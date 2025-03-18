# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from dataclasses import dataclass
from datetime import datetime
from typing import cast

import carb
import carb.events
import omni.timeline
import omni.usd
from omni.earth_2_command_center.app.core.core import get_state
from omni.earth_2_command_center.app.core.time_manager import TimeManager
from omni.earth_2_command_center.app.core.timestamped_sequence import SortedList
from pxr import Sdf, Usd, UsdGeom

from ..features import ProjectedVolumeFeature
from ..settings import PROJECTION_SETTINGS, VOLUME_PRIM_PATH_PREFIX
from .data_loaders import DataLoader
from .events_manager import EventsManager
from .shaders import FieldDescriptor as ShaderFieldDescriptor
from .shaders import RegularVolumeMaterial, SphericalProjectionMaterial
from .volumes import NanoVDBRegularVolume, OpenVDBRegularVolume, RegularVolume, SphericalProjectionVolume


@dataclass
class Field:
    name: str
    volume: RegularVolume
    material: RegularVolumeMaterial
    # volume_xform: UsdGeom.Xform
    loader: DataLoader | None = None


@dataclass
class Fields:
    root: Sdf.Path
    fields: dict[str, Field]
    shader_descs: dict[str, ShaderFieldDescriptor]
    visible: bool = True


class ProjectedVolumeManager:
    _stage: Usd.Stage | None
    _volume_xform: UsdGeom.Xform
    _projected_volume: SphericalProjectionVolume
    _projected_volume_material: SphericalProjectionMaterial

    _features_fields: dict[int, Fields]

    _stage_events_sub: carb.events.ISubscription | None
    _events_manager: EventsManager
    _time_manager: TimeManager
    _timeline_sub: carb.events.ISubscription | None

    _timesteps: dict[str, SortedList]

    _volumes_path = Sdf.Path(VOLUME_PRIM_PATH_PREFIX)
    _create_volume = {
        "vdb": OpenVDBRegularVolume,
        "nvdb": NanoVDBRegularVolume,
    }

    def __init__(self):
        self._stage_events_sub = (
            omni.usd.get_context().get_stage_event_stream().create_subscription_to_pop(self._on_stage_event)
        )
        self._events_manager = EventsManager()
        self._setup_stage()

        self._features_fields = {}

        self._timesteps = {}
        self._time_manager = cast(TimeManager, get_state().get_time_manager())
        self._timeline_sub = None

    def __del__(self):
        self.dispose()

    def release(self):
        self.dispose()

    def dispose(self):
        self._timeline_sub = None
        self._stage_events_sub = None
        self._features_fields.clear()
        self._projected_volume_material.dispose()
        if self._stage is not None:
            self._stage.RemovePrim(self._volume_xform.GetPath())

    def _on_stage_event(self, event: carb.events.IEvent):
        etype = omni.usd.StageEventType(event.type)
        if etype == omni.usd.StageEventType.OPENED:
            self._setup_stage()
        elif etype == omni.usd.StageEventType.CLOSING:
            self._stage.RemovePrim(self._volume_xform.GetPath())
            self.release()

    # def reset(self):
    #     self._reset_material_inputs()
    #     self._features_fields.clear()

    def _setup_stage(self):
        self._stage = cast(Usd.Stage | None, omni.usd.get_context().get_stage())  # type: ignore
        if self._stage is None:
            return

        self._volume_xform = UsdGeom.Xform.Define(self._stage, ProjectedVolumeManager._volumes_path)  # type: ignore
        volume_path = cast(Sdf.Path, self._volume_xform.GetPrim().GetPath())  # type: ignore

        # Projection grid
        self._projected_volume = SphericalProjectionVolume(self._stage, volume_path.AppendChild("SphereGrid"))  # type: ignore
        self._projected_volume.base_radius = PROJECTION_SETTINGS.slab_base_radius
        self._projected_volume.slab_thickness = PROJECTION_SETTINGS.slab_thickness

        # Create the material that will consume the above grids
        self._projected_volume_material = SphericalProjectionMaterial(self._stage, volume_path.AppendChild("SphereMaterial"), PROJECTION_SETTINGS.elevation_colormap, self._projected_volume)  # type: ignore
        self._projected_volume_material.slab_base_radius = PROJECTION_SETTINGS.slab_base_radius
        self._projected_volume_material.slab_thickness = PROJECTION_SETTINGS.slab_thickness

    def _reset_material_inputs(self):
        self._projected_volume_material.release_inputs()

    def _rebuild_material(self):
        active_fields = (field for field in self._features_fields.values() if field.visible)
        shaders_descs = [shader_desc for field in active_fields for shader_desc in field.shader_descs.values()]

        self._projected_volume_material.rebuild_material(shaders_descs)
        self._update_time_mapping(self._time_manager.utc_time)

    def add_feature(self, feature: ProjectedVolumeFeature):
        assert self._stage

        fields_root = cast(
            Sdf.Path, self._volume_xform.GetPath().AppendChild("Fields").AppendChild(f"Feature_{feature.id}")
        )  # type:ignore
        fields: dict[str, Field] = {}
        shader_descs: dict[str, ShaderFieldDescriptor] = {}

        for fieldname, fielddesc in feature.fields.items():
            create_volume = ProjectedVolumeManager._create_volume.get(fielddesc.format)
            if create_volume is None:
                carb.log_warn(f"Unsupported source file type {fielddesc.format} for field {fieldname}. Skipping.")  # type: ignore
                continue

            if (series := fielddesc.series) is not None:
                sl = SortedList()
                numsteps = len(fielddesc.files)
                dt = (series[1] - series[0]) / numsteps
                for i, file in enumerate(fielddesc.files):
                    sl.insert((series[0] + dt * i, file))

                self._timesteps[f"{feature.id}_{fieldname}"] = sl

            vol = create_volume(self._stage, fields_root.AppendChild(fieldname), fielddesc.files, fielddesc.series)
            vol.visible = False
            vol.extent = fielddesc.voxel_range
            vol_mat = RegularVolumeMaterial(
                self._stage, fields_root.AppendChild(fieldname).AppendChild("Material"), fielddesc.colormap, vol
            )

            data_loader = vol.data_loader
            if data_loader:
                self._events_manager.register_update_event(
                    self._stage, f"{feature.id}_{fieldname}", data_loader.get_usd_data_loader().GetPrim().GetPath()
                )

            fields[fieldname] = Field(
                name=f"{feature.id}_{fieldname}",
                volume=vol,
                material=vol_mat,
                loader=data_loader,
            )

            shader_descs[fieldname] = ShaderFieldDescriptor(
                name=f"{feature.id}_{fieldname}",
                volume=vol,
                lat_range=fielddesc.lat_range,
                lon_range=fielddesc.lon_range,
                alt_range=fielddesc.alt_range,
                channel_index=0,  # For now, we always consider one dataset per volume.
                sampler_type=fielddesc.sampler_type,
                zrectilinear_mapping=feature.zrectilinear_mapping,
            )

        self._features_fields[feature.id] = Fields(fields_root, fields, shader_descs)

        self._rebuild_material()
        self._update_time_mapping(self._time_manager.utc_time)

        self._timeline_sub = self._time_manager.get_timeline_event_stream().create_subscription_to_pop(
            self._on_timeline_event
        )

    def remove_feature(self, feature_id: int):
        for field_desc in self._features_fields[feature_id].fields.values():
            if field_desc.loader is not None:
                self._events_manager.unregister_event(self._stage, field_desc.name)

        self._stage.RemovePrim(self._features_fields[feature_id].root)
        del self._features_fields[feature_id]

        if not self._features_fields:
            self._timeline_sub = None

        self._rebuild_material()
        self._update_time_mapping(self._time_manager.utc_time)

    def set_feature_visibility(self, feature: ProjectedVolumeFeature, visible: bool):
        self._features_fields[feature.id].visible = visible
        self._rebuild_material()
        self._update_time_mapping(self._time_manager.utc_time)

    @property
    def slab_base_radius(self):
        return self._projected_volume_material.slab_base_radius

    @slab_base_radius.setter
    def slab_base_radius(self, radius: float):
        self._projected_volume_material.slab_base_radius = radius

    @property
    def slab_thickness(self):
        return self._projected_volume_material.slab_thickness

    @slab_thickness.setter
    def slab_thickness(self, thickness: float):
        self._projected_volume_material.slab_thickness = thickness
        self._projected_volume.slab_thickness = thickness

    @property
    def visible(self):
        return self._volume_scope.GetVisibilityAttr().Get() != UsdGeom.Tokens.invisible

    @visible.setter
    def visible(self, visible: bool):
        self._volume_scope.GetVisibilityAttr().Set(UsdGeom.Tokens.inherited if visible else UsdGeom.Tokens.invisible)

    @property
    def sun_lat(self):
        return self._projected_volume_material.sun_lat

    @sun_lat.setter
    def sun_lat(self, lat: float):
        self._projected_volume_material.sun_lat = lat

    @property
    def sun_lon(self):
        return self._projected_volume_material.sun_lon

    @sun_lon.setter
    def sun_lon(self, lon: float):
        self._projected_volume_material.sun_lon = lon

    @property
    def volume_origin(self):
        return self._projected_volume_material.volume_origin

    @volume_origin.setter
    def volume_origin(self, origin: tuple[float, float, float]):
        self._projected_volume_material.volume_origin = origin

    @property
    def volume_size(self):
        return self._projected_volume_material.volume_size

    @volume_size.setter
    def volume_size(self, size: tuple[float, float, float]):
        self._projected_volume_material.volume_size = size

    def _on_timeline_event(self, event: carb.events.IEvent):
        eventtype = omni.timeline.TimelineEventType(event.type)
        if eventtype in [
            omni.timeline.TimelineEventType.CURRENT_TIME_TICKED_PERMANENT,
            omni.timeline.TimelineEventType.CURRENT_TIME_TICKED,
        ]:
            self._update_time_mapping(self._time_manager.current_utc_time)

    def _update_time_mapping(self, cur_utc_time: datetime | None = None, force_update: bool = False):
        if cur_utc_time is None:
            cur_utc_time = self._time_manager.utc_time

        if not self._timesteps:
            return  # early out

        # Take the first sequence as reference
        sl = list(self._timesteps.values())[0]

        target_idx, _ = sl.find_closest_smaller_equal(cur_utc_time)
        target_idx = target_idx or 0
        current_idx = carb.settings.get_settings().get_as_int("/rtx/index/globalTimestep")

        if current_idx != target_idx:
            carb.settings.get_settings().set_int("/rtx/index/globalTimestep", target_idx)

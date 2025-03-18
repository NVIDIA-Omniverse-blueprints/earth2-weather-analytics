# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from abc import ABC
from datetime import datetime

from omni.earth_2_command_center.app.index.typing import RangeF3D
from pxr import Gf, Sdf, Usd, UsdGeom, UsdVol, Vt

from ..settings import INDEX_RENDER_SETTINGS, PROJECTION_SETTINGS
from .data_loaders import DataLoader, NanoVDBLoader


class Volume(ABC):
    _stage: Usd.Stage
    _volume: UsdVol.Volume

    def __init__(self, stage: Usd.Stage, volumepath: Sdf.Path):
        self._stage = stage
        self._volume = UsdVol.Volume.Define(stage, volumepath)  # type: ignore
        self._volume.CreateVisibilityAttr().Set(UsdGeom.Tokens.inherited)  # type: ignore

        volume_prim: Usd.Prim = self._volume.GetPrim()  # type: ignore
        volume_prim.CreateAttribute("omni:rtx:skip", Sdf.ValueTypeNames.Bool, custom=True).Set(1)
        volume_prim.CreateAttribute("nvindex:composite", Sdf.ValueTypeNames.Bool, custom=True).Set(1)
        volume_prim.CreateAttribute("outputs:volume", Sdf.ValueTypeNames.Token, custom=False)

    def __del__(self):
        self.dispose()

    def dispose(self):
        self._stage.RemovePrim(self._volume.GetPrim().GetPath())

    @property
    def volume(self) -> UsdVol.Volume:
        return self._volume

    @property
    def data_loader(self) -> DataLoader | None:
        return None

    @property
    def visible(self) -> bool:
        return self._volume.GetVisibilityAttr().Get() != UsdGeom.Tokens.invisible

    @visible.setter
    def visible(self, visible: bool):
        self._volume.GetVisibilityAttr().Set(UsdGeom.Tokens.inherited if visible else UsdGeom.Tokens.invisible)

    @property
    def extent(self) -> RangeF3D | None:
        float3s = self._volume.GetExtentAttr().Get()
        if float3s:
            return (float3s[0], float3s[1])
        else:
            return None

    @extent.setter
    def extent(self, range: RangeF3D):
        self._volume.GetExtentAttr().Set([range[0], range[1]])


class RegularVolume(Volume):
    _volume_asset: UsdVol.OpenVDBAsset

    def __init__(self, stage: Usd.Stage, volumepath: Sdf.Path):
        super().__init__(stage, volumepath)

        self._volume_asset = UsdVol.OpenVDBAsset.Define(stage, volumepath.AppendChild("VolumeAsset"))
        self._volume.CreateFieldRelationship("volume", self._volume_asset.GetPath())

    def __del__(self):
        self.dispose()
        super().__del__()

    def dispose(self):
        self._stage.RemovePrim(self._volume_asset.GetPrim().GetPath())
        super().dispose()


class OpenVDBRegularVolume(RegularVolume):
    def __init__(
        self, stage: Usd.Stage, volumepath: Sdf.Path, files: list[str], series: tuple[datetime, datetime] | None
    ):
        super().__init__(stage, volumepath)
        filepathattr = self._volume_asset.CreateFilePathAttr()
        if len(files) == 1:
            filepathattr.Set(files[0])
        else:
            assert series
            tcpersec = stage.GetTimeCodesPerSecond()
            dt = (series[1] - series[0]) / len(files)
            for i, file in enumerate(files):
                tc = (series[0] + dt * i).timestamp()
                filepathattr.Set(file, Usd.TimeCode(tc / tcpersec))


class NanoVDBRegularVolume(RegularVolume):
    _data_loader: NanoVDBLoader

    def __init__(
        self, stage: Usd.Stage, volumepath: Sdf.Path, files: list[str], series: tuple[datetime, datetime] | None
    ):
        super().__init__(stage, volumepath)
        self._volume_asset.CreateFilePathAttr().Set("nothing")
        volume_asset_prim = self._volume_asset.GetPrim()
        volume_asset_prim.SetCustomDataByKey(
            "nvindex.importerSettings:importer",
            Vt.Token("nv::index::plugin::openvdb_integration.NanoVDB_empty_init_importer"),
        )
        volume_asset_prim.SetCustomDataByKey("nvindex.importerSettings:is_verbose", True)
        volume_asset_prim.SetCustomDataByKey("nvindex.importerSettings:nb_attributes", 10)
        volume_asset_prim.SetCustomDataByKey("nvindex.importerSettings:nanovdb_compression", "nanovdb_fp8")

        self._data_loader = NanoVDBLoader(stage, volumepath.AppendChild("DataLoader"), files, series)

    @property
    def data_loader(self) -> NanoVDBLoader:
        return self._data_loader


class SphericalProjectionVolume(Volume):
    _field_asset: UsdVol.FieldAsset

    def __init__(self, stage: Usd.Stage, volumepath: Sdf.Path):
        super().__init__(stage, volumepath)
        icon_volume_prim = self._volume.GetPrim()

        # add XAC specific custom data and attribues
        icon_volume_prim.SetCustomDataByKey("nvindex.renderSettings", INDEX_RENDER_SETTINGS)
        icon_volume_prim.CreateAttribute("omni:rtx:skip", Sdf.ValueTypeNames.Bool, custom=True).Set(1)
        icon_volume_prim.CreateAttribute("nvindex:composite", Sdf.ValueTypeNames.Bool, custom=True).Set(1)
        icon_volume_prim.CreateAttribute("nvindex:type", Sdf.ValueTypeNames.Token, custom=True).Set("irregular_volume")
        icon_volume_prim.CreateAttribute("outputs:volume", Sdf.ValueTypeNames.Token, custom=False)

        # now create Icon Grid asset
        field_asset_prim: Usd.Prim = stage.DefinePrim(volumepath.AppendChild("netcdf"), "FieldAsset")
        self._field_asset = UsdVol.FieldAsset(field_asset_prim)

        self._volume.CreateFieldRelationship("netcdf", field_asset_prim.GetPath())

        # setup custom data for the field importer
        field_asset_prim.SetCustomData(
            {
                "nvindex.importerSettings": {
                    "attr::0::variable": Vt.Token("unused"),
                    "center_offset": Gf.Vec3f(PROJECTION_SETTINGS.center),
                    "height_range": Gf.Vec2f(
                        *PROJECTION_SETTINGS.height_range
                    ),  # Only consider two layers of data. One would be good, but the importer does let us go down.
                    "height_scale": Vt.Float(PROJECTION_SETTINGS.height_scale),  # Each layer will be a hundred thick
                    "importer": Vt.Token("nv::index::plugin::icon_importer.Icon_irregular_volume_generator"),
                    "input_file_grid": Sdf.AssetPath(str(PROJECTION_SETTINGS.icon_grid_path)),
                    "projection": Vt.Token("spherical"),
                    "spherical_radius": Vt.Float(
                        PROJECTION_SETTINGS.slab_base_radius - PROJECTION_SETTINGS.slab_thickness
                    ),  # Our spherical radius is our base earth radius (4950) + some slack to get above the atmosphere (100 here)
                    "timestep": Vt.Int(0),
                }
            }
        )

    def __del__(self):
        self.dispose()
        super().__del__()

    def dispose(self):
        self._stage.RemovePrim(self._field_asset.GetPrim().GetPath())
        super().dispose()

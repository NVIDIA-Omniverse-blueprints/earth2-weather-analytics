# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import re
from datetime import datetime, timedelta
import dateutil
from functools import partial
from glob import glob
from os.path import basename, splitext
from typing import Any, cast

import carb
import omni.ext
import omni.kit.async_engine as async_engine
from carb.settings import get_settings
from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.features_api import FeaturesAPI
from omni.earth_2_command_center.app.window.feature_properties import get_instance

from . import colormaps
from .core import Colormap, ProjectedVolumeFeatureDesc, VariableDesc
from .features import ProjectedVolumeFeature  # , XACTimestampedSequence
from .settings import PROJECTION_SETTINGS
from .shading.volume_feature_manager import VolumeFeatureManager
from .tools.shader_watcher import shader_watcher
from .typing import FileFormatType, RangeF1D, RangeI3D, ShaderSamplerType


# The regex-based implementation was flagged by SonarQube as "vulnerable to polynomial runtime due to backtracking".
# @Thomas Arcila has provided both an improved regex (which unfortunately requires Python 3.11), as well as the non-regex
# implementation that is in use below.
# improved regex (Python 5.11):
# pattern = r"_x1\.(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})-(?P<base_offset>[\d]++)_[^_]++_(?P<k>\d++)x(?P<j>\d++)x(?P<i>\d++)_[^_]++_T(?P<offset>\d++)"
#
# def parseTimeSCREAM(fname: str) -> datetime:
#     # rgr_output.scream.Cess.timestep.combined.INSTANT.nsteps_x1.2020-08-04-00100_cloud_101x4000x8000_float32_T0000_fpn.nvdb

#     pattern = r"_x1\.(?P<year>[\d]+)-(?P<month>[\d]+)-(?P<day>[\d]+)-(?P<base_offset>[\d]+).*_(?P<k>[\d]+)x(?P<j>[\d]+)x(?P<i>[\d]+)_.*_T(?P<offset>[\d]+)"
#     regex = re.compile(pattern)
#     if m := regex.search(fname):
#         g = m.groupdict()
#         offset = timedelta(seconds=int(g["base_offset"]) + int(g["offset"]) * 100)
#         date = datetime(int(g["year"]), int(g["month"]), int(g["day"])) + offset
#         # carb.log_error(f'{fname}={date.ctime()}')
#         return date
#     raise RuntimeError(f"Unsupported format {fname}")

def parseTimeSCREAM(fname: str) -> datetime:
    try:
        _, name = fname.split("_x1.", 2)
        date_baseoffset, name, dims, type, offset, _ = name.split("_", 6)
        year, month, day, baseoffset = date_baseoffset.split("-", 4)
        assert(offset[0] == "T")
        offset = offset[1:]
        offset = timedelta(seconds=int(baseoffset) + int(offset) * 100)
        date = datetime(int(year), int(month), int(day)) + offset
        return date
    except:
        raise RuntimeError(f"Unsupported format {fname}")


class Extension(omni.ext.IExt):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._data_path = None

    def on_startup(self, ext_id: str):
        settings = get_settings()
        self._data_path = settings.get_as_string("/exts/omni.earth_2_command_center.app.index/data_path")

        features_api = get_state().get_features_api()
        self._volume_feature_manager = VolumeFeatureManager(features_api)

        self._registered_names = []
        async_engine.run_coroutine(self._discover_datasets())

    def on_shutdown(self):
        if shader_watcher is not None:
            shader_watcher.dispose()
        self._volume_feature_manager.dispose()
        self._unregister_add_callbacks()

    def _register_add_callback(self, name, callback):
        feature_properties = get_instance()
        feature_properties.register_feature_type_add_callback(name, callback)
        self._registered_names.append(name)

    def _unregister_add_callbacks(self):
        feature_properties = get_instance()
        for name in self._registered_names:
            feature_properties.unregister_feature_type_add_callback(name)
        self._registered_names = []

    def _find_dataset(self, name: str):
        import glob

        matches = glob.glob(f"{self._data_path}/**/{name}", recursive=True)
        if matches:
            return sorted(matches)
        return None

    def _try_add_h7_ll_new_cloud(self):
        paths = self._find_dataset("h7_ll_new_cloud_128x4000x8000_float32_T0002.vdb")
        if not paths:
            carb.log_info('"h7_ll_new_cloud_128x4000x8000_float32_T0002.vdb" not found!')
            return

        path = paths[0]

        variables = [
            VariableDesc("default", "vdb", [path], "float", colormaps.GreyRamp(domain=(0.0, 0.001))),
        ]

        desc = ProjectedVolumeFeatureDesc(
            name="h7_ll_new_cloud",
            variables=variables,
            latitude_range=(-90.0, 90.0),
            longitude_range=(-180.0, 180.0),
            voxel_range=((0, 0, 0), (8000, 4000, 113)),
            altitude_range=(PROJECTION_SETTINGS.slab_base_radius, PROJECTION_SETTINGS.slab_base_radius + 100),
            series=None,
            elevation_colormap=colormaps.AtmosphericScattering(),
        )

        self._register_add_callback("h7_ll_new_cloud", lambda desc=desc: self._add_feature(desc))

    def _try_add_rgr_output_scream_cess(self):
        paths = self._find_dataset(
            "data-fpn-perlmutter/rgr_output.scream.Cess.timestep.combined.INSTANT.nsteps_x1*.nvdb"
        )
        if not paths:
            carb.log_info(
                '"data-fpn-perlmutter/rgr_output.scream.Cess.timestep.combined.INSTANT.nsteps_x1*.nvdb" not found!'
            )
            return

        variables = [
            VariableDesc("default", "nvdb", paths, "FpN", colormaps.GreyRamp(domain=(0.0, 0.2))),
        ]

        desc = ProjectedVolumeFeatureDesc(
            name="rgr_output_scream_Cess",
            variables=variables,
            latitude_range=(-90.0, 90.0),
            longitude_range=(-180.0, 180.0),
            voxel_range=((0, 0, 0), (8000, 4000, 101)),
            altitude_range=(PROJECTION_SETTINGS.slab_base_radius, PROJECTION_SETTINGS.slab_base_radius + 100),
            series=None,
            elevation_colormap=colormaps.AtmosphericScattering(),
        )

        self._register_add_callback(
            f'rgr_output.scream.Cess{"(timesteps)" if len(paths) > 1 else ""}',
            lambda desc=desc: self._add_feature(desc),
        )

    def _try_add_taiwan_wrf_simulation(
        self,
        resolution: str,
        format: FileFormatType,
        shader_sampler_type: ShaderSamplerType,
        latitude_range: RangeF1D,
        longitude_range: RangeF1D,
        altitude_range: RangeF1D,
        voxel_range: RangeI3D,
        zrectilinear_mapping: list[float] | None = None,
    ):

        paths = self._find_dataset(f"wrf_simulation/{resolution}/{format}/*/*.{format}")
        if not paths:
            carb.log_info(f"Cannot find Taiwan Typhoon dataset ({resolution}), skipping...")
            return

        carb.log_info(f"Adding taiwan_typhoon_{resolution} feature")
        cloud = [path for path in paths if "/qcloud/QCLOUD_" in path]  # type: ignore
        ice = [path for path in paths if "/qice/QICE_" in path]  # type: ignore
        rain = [path for path in paths if "/qrain/QRAIN_" in path]  # type: ignore
        snow = [path for path in paths if "/qsnow/QSNOW_" in path]  # type: ignore

        cloudlen = len(cloud)
        variables = {
            "cloud": cloud,
        }

        for varname in ["ice", "rain", "snow"]:
            var: list[str] = locals().get(varname, [])
            if var and cloudlen == len(var):
                variables[varname] = var
            else:
                carb.log_warn(
                    f"Variable {varname} does not have the expected number of time samples ({len(var)} instead of {cloudlen}). Skipping."
                )

        # WORKAROUND WHAT SEEMS TO BE AN INDEX BUG, ONLY LOAD TWO VARIABLES SO IT DOES LESS LIKELY BREAK THE LOADING
        variablesdesc = [
            VariableDesc(name, format, files, shader_sampler_type, colormaps.Clouds(domain=(0.00001, 0.0005)))
            for name, files in variables.items()
            if name in ("cloud", "ice")
        ]

        starttime = dateutil.parser.isoparser("2021-09-12 09:00:00.000000Z")
        endtime = starttime + timedelta(seconds=60) * cloudlen

        desc = ProjectedVolumeFeatureDesc(
            name=f"Taiwan typhoon {resolution}",
            variables=variablesdesc,
            latitude_range=latitude_range,
            longitude_range=longitude_range,
            voxel_range=voxel_range,
            altitude_range=(
                PROJECTION_SETTINGS.slab_base_radius + altitude_range[0],
                PROJECTION_SETTINGS.slab_base_radius + altitude_range[1],
            ),
            series=(starttime, endtime),
            elevation_colormap=colormaps.AtmosphericScattering(),
            zrectilinear_mapping=zrectilinear_mapping,
        )

        self._register_add_callback(
            f"Taiwan typhoon ({resolution}, timesteps)", lambda desc=desc: self._add_feature(desc)
        )

    async def _discover_datasets(self):
        self._try_add_h7_ll_new_cloud()
        self._try_add_rgr_output_scream_cess()

        format = "nvdb"
        sampler: dict[FileFormatType, ShaderSamplerType] = {
            "nvdb": "Fp16",
            "vdb": "float",
        }

        self._try_add_taiwan_wrf_simulation(
            resolution="1km",
            format=format,
            shader_sampler_type=sampler[format],
            latitude_range=(22.4563152882, 22.4563152882 + 389 * 0.00896305764),
            longitude_range=(119.1968293233, 119.1968293233 + 389 * 0.00984586466000001),
            altitude_range=(0.0533747, 20.76771),
            voxel_range=((0, 0, 0), (389, 389, 60)),
            zrectilinear_mapping=[
                0.0,
                0.0576518,
                0.0966279,
                0.118053,
                0.13462,
                0.149891,
                0.164164,
                0.178092,
                0.191701,
                0.20499,
                0.21796,
                0.230609,
                0.242938,
                0.254947,
                0.266636,
                0.27804,
                0.289514,
                0.301155,
                0.312962,
                0.324936,
                0.337076,
                0.349383,
                0.361856,
                0.374495,
                0.387301,
                0.400274,
                0.413413,
                0.426718,
                0.44019,
                0.453828,
                0.467634,
                0.481612,
                0.495759,
                0.510078,
                0.524566,
                0.539226,
                0.554056,
                0.569056,
                0.584228,
                0.599569,
                0.615076,
                0.630697,
                0.646419,
                0.662242,
                0.678167,
                0.694193,
                0.71032,
                0.726549,
                0.74288,
                0.759311,
                0.775844,
                0.792479,
                0.809215,
                0.826052,
                0.84299,
                0.86003,
                0.877172,
                0.894414,
                0.911759,
                0.929204,
                0.946751,
                0.964399,
                0.982149,
                1.0,
            ],
        )

        self._try_add_taiwan_wrf_simulation(
            resolution="200m",
            format="vdb",
            shader_sampler_type=sampler["vdb"],
            latitude_range=(24.02829, 24.02829 + 700 * 0.00178222857),
            longitude_range=(121.3759, 121.3759 + 700 * 0.00199157141999999),
            altitude_range=(0.02283588, 20.58393),
            voxel_range=((0, 0, 0), (700, 700, 120)),
            zrectilinear_mapping=[
                0.0,
                0.0647794,
                0.108603,
                0.131841,
                0.147675,
                0.162683,
                0.176957,
                0.190874,
                0.204475,
                0.217759,
                0.230727,
                0.243378,
                0.255713,
                0.267732,
                0.279434,
                0.29082,
                0.301933,
                0.313134,
                0.324501,
                0.336033,
                0.347731,
                0.359595,
                0.371624,
                0.383819,
                0.39618,
                0.408706,
                0.421398,
                0.434255,
                0.447278,
                0.460467,
                0.473821,
                0.487342,
                0.50104,
                0.514919,
                0.52898,
                0.543223,
                0.557648,
                0.572255,
                0.587043,
                0.602013,
                0.617165,
                0.632498,
                0.647998,
                0.663615,
                0.679346,
                0.695192,
                0.711153,
                0.727227,
                0.743417,
                0.759721,
                0.776139,
                0.792672,
                0.80932,
                0.826082,
                0.842958,
                0.85995,
                0.877055,
                0.894275,
                0.91161,
                0.929059,
                0.946622,
                0.9643,
                0.982093,
                1.0,
            ],
        )

        # self._try_add_taiwan_wrf_simulation(
        #     resolution="100m", format='vdb',
        #     shader_sampler_type=sampler['vdb'],
        #     latitude_range=(24.95753, 24.95753 + 200 * 0.0008911),
        #     longitude_range=(121.4735, 121.4735 + 200 * 0.000992),
        #     altitude_range=(0.02283588, 20.58393),
        #     voxel_range=((0, 0, 0), (200, 200, 120)),
        # )

    def _add_feature(self, feature_desc: ProjectedVolumeFeatureDesc, active: bool = True):
        features_api: FeaturesAPI = get_state().get_features_api()

        volume = features_api.create_feature(ProjectedVolumeFeature, feature_desc=feature_desc)
        features_api.add_feature(volume)
        get_state().get_time_manager().include_all_features(playback_duration=3)

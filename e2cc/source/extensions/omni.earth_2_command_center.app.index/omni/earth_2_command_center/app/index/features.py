# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import pathlib
from dataclasses import dataclass
from datetime import datetime

import carb
import omni.kit.app
import omni.timeline
from omni.earth_2_command_center.app.core.features_api import FeaturesAPI, Volume

from .core import Colormap, ProjectedVolumeFeatureDesc
from .typing import FileFormatType, RangeF1D, RangeI3D, ShaderSamplerType

EXTENSION_FOLDER_PATH = pathlib.Path(
    omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)  # type: ignore
)


@dataclass
class Field:
    files: list[str]
    colormap: Colormap
    voxel_range: RangeI3D
    lat_range: RangeF1D
    lon_range: RangeF1D
    alt_range: RangeF1D
    format: FileFormatType
    sampler_type: ShaderSamplerType = "float"
    series: tuple[datetime, datetime] | None = None


class ProjectedVolumeFeature(Volume):
    feature_type = "Projected Volume"
    _fields: dict[str, Field]
    _time_coverage: tuple[datetime, datetime] | None

    _zrectilinear_mapping: list[float] | None

    def __init__(self, features_api: FeaturesAPI, feature_id: int, feature_desc: ProjectedVolumeFeatureDesc):
        super().__init__(features_api=features_api, feature_id=feature_id)

        self._name = feature_desc.name
        self._elevation_colormap = feature_desc.elevation_colormap
        self._fields = {}

        self._time_coverage = feature_desc.series

        self._zrectilinear_mapping = feature_desc.zrectilinear_mapping

        for variable_desc in feature_desc.variables:
            series = variable_desc.series or feature_desc.series

            if len(variable_desc.files) > 1 and series is None:
                carb.log_error(
                    f"Series information (start time and delta) missing for variable {variable_desc.name}. Keeping on the first file."
                )
                variable_desc.files = [variable_desc.files[0]]

            if series is not None:
                self._time_coverage = (
                    series
                    if self._time_coverage is None
                    else (
                        min(self._time_coverage[0], series[0]),
                        max(self._time_coverage[1], series[1]),
                    )
                )

            field = Field(
                files=variable_desc.files,
                colormap=variable_desc.colormap,
                voxel_range=feature_desc.voxel_range,
                lat_range=feature_desc.latitude_range,
                lon_range=feature_desc.longitude_range,
                alt_range=feature_desc.altitude_range,
                format=variable_desc.format,
                sampler_type=variable_desc.shader_sampler_type,
                series=series,
            )

            self._fields[variable_desc.name] = field

    @property
    def time_coverage(self):
        return self._time_coverage

    @time_coverage.setter
    def time_coverage(self, time_coverage: tuple[datetime, datetime]):
        carb.log_warn(f"Setting time coverage on a ProjectedVolumeFeature is not supported. Ignoring.")

    @property
    def fields(self):
        return self._fields

    @property
    def zrectilinear_mapping(self):
        return self._zrectilinear_mapping

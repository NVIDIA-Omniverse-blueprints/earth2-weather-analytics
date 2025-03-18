# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from dataclasses import dataclass, field
from datetime import datetime

from .colormaps import AtmosphericScattering, Colormap, GreyRamp
from .typing import FileFormatType, RangeF1D, RangeI3D, ShaderSamplerType


@dataclass
class VariableDesc:
    name: str
    format: FileFormatType
    files: list[str]
    shader_sampler_type: ShaderSamplerType
    colormap: Colormap = field(default_factory=GreyRamp)
    series: tuple[datetime, datetime] | None = None


@dataclass
class ProjectedVolumeFeatureDesc:
    name: str
    variables: list[VariableDesc] = field(default_factory=list)
    elevation_colormap: Colormap = field(default_factory=AtmosphericScattering)
    voxel_range: RangeI3D = ((0, 0, 0), (1, 1, 1))
    latitude_range: RangeF1D = (-90.0, 90.0)
    longitude_range: RangeF1D = (-180.0, 180.0)
    altitude_range: RangeF1D = (4950, 5050)
    series: tuple[datetime, datetime] | None = None
    zrectilinear_mapping: list[float] | None = None

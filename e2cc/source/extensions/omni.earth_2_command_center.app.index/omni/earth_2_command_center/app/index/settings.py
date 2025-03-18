# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

import carb.settings
import omni.kit.app
from pxr import Vt

from .colormaps import AtmosphericScattering
from .core import Colormap
from .typing import Float3, RangeF1D

WATCH_SHADERS = carb.settings.get_settings().get_as_bool("/exts/omni.earth_2_command_center.app.index/watch_shaders")

INDEX_RENDER_SETTINGS = {
    "diagnosticsMode": Vt.Int(0),
    "diagnosticsFlags": Vt.Int(8),
    "samplingMode": Vt.Int(1),
    "samplingReferenceSegmentLength": Vt.Float(1),
    "samplingSegmentLength": Vt.Double(0.75),
}

DATA_PATH = Path(omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)) / "data"
GRID_PATH = DATA_PATH
SHADERS_PATH = DATA_PATH / "shaders"

VOLUME_PRIM_PATH_PREFIX = "/World/Volumes"


@dataclass
class ProjectionSettings:
    # General projection settings
    slab_base_radius: float = 4950.0
    slab_thickness: float = 100  # 25.0
    elevation_colormap: Colormap = field(default_factory=AtmosphericScattering)

    # Icon importer specifics
    icon_grid_path: Path = DATA_PATH / "icon_grid_0013_R02B04_R.nc"
    center: Float3 = field(default_factory=lambda: deepcopy((0.0, 0.0, 0.0)))
    height_range: RangeF1D = field(default_factory=lambda: deepcopy((0.0, 2.0)))
    height_scale: float = 100  # 25.0  # must be the same as slab_thickness


PROJECTION_SETTINGS = ProjectionSettings()

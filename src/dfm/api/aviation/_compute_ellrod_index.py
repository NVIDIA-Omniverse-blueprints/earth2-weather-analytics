# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Compute Ellrod Turbulence Index from wind and temperature fields."""

from typing import Literal
from .. import FunctionCall, FunctionRef


class ComputeEllrodIndex(FunctionCall, frozen=True):
    """
    Compute Ellrod Turbulence Index (TI1) at a given pressure level.

    Uses horizontal deformation and vertical wind shear to estimate
    clear-air turbulence probability. TI1 = VWS * DEF where VWS is
    vertical wind shear and DEF is total deformation.

    Args:
        data: FunctionRef for xarray.Dataset with u/v wind and temperature
        pressure_level: Target pressure level in hPa (default 300 for jet stream)
        output_name: Name of the output turbulence index variable
    """

    api_class: Literal["dfm.api.aviation.ComputeEllrodIndex"] = (
        "dfm.api.aviation.ComputeEllrodIndex"
    )
    data: FunctionRef
    pressure_level: int = 300
    output_name: str = "ellrod_ti"

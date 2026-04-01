# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Compute crosswind and headwind components relative to a runway."""

from typing import Literal
from .. import FunctionCall, FunctionRef


class ComputeCrosswind(FunctionCall, frozen=True):
    """
    Decompose surface winds into crosswind and headwind components
    relative to a runway heading at a given airport location.

    Args:
        data: FunctionRef for xarray.Dataset with u10m/v10m surface winds
        runway_heading: Runway heading in degrees true (0-360)
        airport_lat: Airport latitude
        airport_lon: Airport longitude
        output_name: Name prefix for output variables (creates {name}_cross and {name}_head)
    """

    api_class: Literal["dfm.api.aviation.ComputeCrosswind"] = (
        "dfm.api.aviation.ComputeCrosswind"
    )
    data: FunctionRef
    runway_heading: float
    airport_lat: float
    airport_lon: float
    output_name: str = "crosswind"

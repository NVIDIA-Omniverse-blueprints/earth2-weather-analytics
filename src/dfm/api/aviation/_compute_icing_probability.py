# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Compute icing probability from temperature and humidity fields."""

from typing import Literal
from .. import FunctionCall, FunctionRef


class ComputeIcingProbability(FunctionCall, frozen=True):
    """
    Compute icing probability based on temperature and relative humidity.

    Uses a threshold model: icing occurs when temperature is in the
    supercooled range and relative humidity exceeds the threshold.
    P_ice = max(0, (RH - rh_threshold) / (100 - rh_threshold))
    where temperature is in [temp_range_min, temp_range_max] Celsius.

    Args:
        data: FunctionRef for xarray.Dataset with temperature and humidity
        temp_range_min: Minimum temperature for icing (Celsius)
        temp_range_max: Maximum temperature for icing (Celsius)
        rh_threshold: Minimum relative humidity percentage for icing
        output_name: Name of the output icing probability variable
    """

    api_class: Literal["dfm.api.aviation.ComputeIcingProbability"] = (
        "dfm.api.aviation.ComputeIcingProbability"
    )
    data: FunctionRef
    temp_range_min: float = -20.0
    temp_range_max: float = 0.0
    rh_threshold: float = 70.0
    output_name: str = "icing_prob"

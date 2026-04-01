# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Compute vertical wind shear from u/v wind components at pressure levels."""

from typing import List, Literal, Optional, Tuple
from .. import FunctionCall, FunctionRef


class ComputeWindShear(FunctionCall, frozen=True):
    """
    Compute vertical wind shear between pressure levels.

    Takes u/v wind components at multiple pressure levels and computes
    the magnitude of the wind shear vector (dV/dp) between adjacent
    or specified level pairs.

    Args:
        data: FunctionRef for xarray.Dataset with u/v wind at pressure levels
        level_pairs: Optional list of (lower, upper) pressure level pairs in hPa.
                     If None, computes between all adjacent levels.
        output_name: Name of the output wind shear variable
    """

    api_class: Literal["dfm.api.aviation.ComputeWindShear"] = (
        "dfm.api.aviation.ComputeWindShear"
    )
    data: FunctionRef
    level_pairs: Optional[List[Tuple[int, int]]] = None
    output_name: str = "wind_shear"

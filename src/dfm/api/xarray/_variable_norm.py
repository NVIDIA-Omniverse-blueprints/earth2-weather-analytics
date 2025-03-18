# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import List, Literal
from .. import FunctionCall, FunctionRef


class VariableNorm(FunctionCall, frozen=True):
    """
    Function to compute the p-norm across multiple variables in an xarray Dataset.
    Returns a new Dataset containing only the computed norm.

    Args:
        data: FunctionRef for the xarray.Dataset
        variables: List of variables to include in norm calculation
        p: The order of the norm (default=2 for Euclidean norm)
        output_name: Name of the output variable (default="norm")
    """

    api_class: Literal["dfm.api.xarray.VariableNorm"] = "dfm.api.xarray.VariableNorm"
    data: FunctionRef
    variables: List[str]
    p: float = 2.0
    output_name: str = "norm"

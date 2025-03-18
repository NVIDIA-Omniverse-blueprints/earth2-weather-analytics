# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

""""""

from typing import Literal
from .. import FunctionCall, FunctionRef


class AveragePointwise(FunctionCall, frozen=True):
    """
    Function to compute the pointwise average between two xarrays of the same
    shape.

    Args:
        lhs: The first xarray.Dataset.
        rhs: The second xarray.Dataset.

    Function Returns:
        xarray.Dataset with the same shape containing the pointwise average.

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.xarray.AveragePointwise"] = (
        "dfm.api.xarray.AveragePointwise"
    )
    lhs: FunctionRef
    rhs: FunctionRef

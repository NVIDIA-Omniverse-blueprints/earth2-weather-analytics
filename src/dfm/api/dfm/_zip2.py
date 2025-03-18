# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""FunctionParams for an echo, mainly for testing"""

from typing import Literal
from .. import FunctionCall, FunctionRef


class Zip2(FunctionCall, frozen=True):
    """
    Function to pair up results from two FunctionRefs.
    Both lhs and rhs functions must produce the same number
    of results.

    Args:
        lhs: The lhs function.
        rhs: The rhs function.

    Function Returns:
        A tuple (lhs_result, rhs_result) for each pair of results.

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.Zip2"] = "dfm.api.dfm.Zip2"
    lhs: FunctionRef
    rhs: FunctionRef

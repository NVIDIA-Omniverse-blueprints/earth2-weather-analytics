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

from pydantic import JsonValue
from .. import FunctionCall


class Constant(FunctionCall, frozen=True):
    """
    Function that returns a constant json value.

    Args:
        value: The json value to return.

    Function Returns:
        The given json value.

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.Constant"] = "dfm.api.dfm.Constant"
    value: JsonValue

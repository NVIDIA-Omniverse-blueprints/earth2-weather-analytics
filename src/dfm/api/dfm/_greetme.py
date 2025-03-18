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
from .. import FunctionCall


class GreetMe(FunctionCall, frozen=True):
    """
    Function that returns a greeting. This function is mainly used for testing as the
    "Hello World". The returned greeting is a combination of a provider-configured
    greeting and the client supplied name.

    Args:
        name: String that gets combined with the provider-configured greeting.

    Function Returns:
        The greeting as a string.

    Client Returns:
        A ValueResponse with the greeting as a string.
    """

    api_class: Literal["dfm.api.dfm.GreetMe"] = "dfm.api.dfm.GreetMe"
    name: str

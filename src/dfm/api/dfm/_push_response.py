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
from dfm.api.response import Response
from .. import FunctionCall


class PushResponse(FunctionCall, frozen=True):
    """
    Function to push a response onto the response queue from where
    the client polls. This function is not really intended to be
    used by the client but is used by the DFM internally to return
    information back to the client. Remote sites pack a PushResponse
    function inside an Execute block and send it back to the client's
    home site.

    Args:
        response: The response object that gets pushed onto the response queue.

    Function Returns:
        -

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.PushResponse"] = "dfm.api.dfm.PushResponse"
    response: Response

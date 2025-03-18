# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Literal
from ._response_body import ResponseBody


class StatusResponse(ResponseBody, frozen=True):
    """
    ResponseBody carrying a simple status message.

    Args:
        originating_site: The site where this status message was sent from.
        message: The status string.
    """

    api_class: Literal["dfm.api.response.StatusResponse"] = (
        "dfm.api.response.StatusResponse"
    )
    originating_site: str
    message: str

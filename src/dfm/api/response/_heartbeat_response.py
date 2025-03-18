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


class HeartbeatResponse(ResponseBody, frozen=True):
    """
    A ResponseBody that represents a heartbeat from the given site to the client.
    """

    api_class: Literal["dfm.api.response.HeartbeatResponse"] = (
        "dfm.api.response.HeartbeatResponse"
    )
    originating_site: str

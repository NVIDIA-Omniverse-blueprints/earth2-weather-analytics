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


class ErrorResponse(ResponseBody, frozen=True):
    """
    ResponseBody containing an error.

    Args:
        http_status_code: An HTTP status code correlating to this error.
        message: A short description of the error.
        traceback: A detailed traceback of the exception that caused this error response.
    """

    api_class: Literal["dfm.api.response.ErrorResponse"] = (
        "dfm.api.response.ErrorResponse"
    )
    http_status_code: int
    message: str
    traceback: str

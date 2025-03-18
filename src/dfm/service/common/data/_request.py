#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


"""
Common data types used by services
"""

from pydantic import BaseModel

from dfm.api.response import Response
from ....api import Process


class RequestState(BaseModel):
    """
    Data that we need to store to handle request processing in DFM
    """

    request_id: str
    body: Process
    responses: list[Response] = []

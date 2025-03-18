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

# -*- coding: utf-8 -*-

from enum import Enum


def normalize_url(url: str) -> str:
    """
    Makes sure that the URL starts with https and ends without any slashes
    """
    if not url.startswith("https") and not url.startswith("http"):
        url = f"https://{url}"
    return url.rstrip("/")


class RequestType(Enum):
    """
    Defines what request should be used for given http request
    """

    Post = "POST"
    Get = "GET"
    Delete = "DELETE"

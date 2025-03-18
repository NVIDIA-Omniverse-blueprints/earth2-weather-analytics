# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Configuration of a whole site"""
from typing import Dict, Optional
from pydantic import BaseModel
from .resource import ResourceConfigs
from .provider import ProviderConfig


class SiteConfig(BaseModel, frozen=True):
    """Configuration of a whole site"""

    site: str
    contact: Optional[str] = None
    heartbeat_interval: float = 15.0  # in s
    resources: Optional[ResourceConfigs] = None
    providers: Dict[str, ProviderConfig]

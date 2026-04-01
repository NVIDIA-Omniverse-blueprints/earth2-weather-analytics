# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Configuration for Aviation Weather Center TAF Data Loader."""

from typing import Literal
from .._adapter_config import AdapterConfig


class LoadTafData(AdapterConfig, frozen=True):
    """Config for LoadTafData Adapter."""

    adapter_class: Literal["adapter.aviation.LoadTafData"] = (
        "adapter.aviation.LoadTafData"
    )
    awc_url: str = "https://aviationweather.gov/api/data/taf"
    request_timeout: int = 30
    request_retries: int = 3

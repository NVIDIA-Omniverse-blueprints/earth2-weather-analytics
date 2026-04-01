# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Configuration for Aviation Weather Center SIGMET/AIRMET Data Loader."""

from typing import Literal
from .._adapter_config import AdapterConfig


class LoadSigmetData(AdapterConfig, frozen=True):
    """Config for LoadSigmetData Adapter."""

    adapter_class: Literal["adapter.aviation.LoadSigmetData"] = (
        "adapter.aviation.LoadSigmetData"
    )
    awc_url: str = "https://aviationweather.gov/api/data/airsigmet"
    request_timeout: int = 30
    request_retries: int = 3

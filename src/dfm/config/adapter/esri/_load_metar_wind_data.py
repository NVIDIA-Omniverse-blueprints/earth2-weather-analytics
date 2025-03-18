# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Configuration for NOAA METAR Wind Data Loader"""

from typing import Literal
from .._adapter_config import AdapterConfig


class LoadMetarWindData(AdapterConfig, frozen=True):
    """Config for LoadMetarWindData Adapter"""

    adapter_class: Literal["adapter.esri.LoadMetarWindData"] = (
        "adapter.esri.LoadMetarWindData"
    )
    metar_wind_server: str = (
        "https://services9.arcgis.com/RHVPKKiFTONKtxq3/arcgis/rest/services/NOAA_METAR_current_wind_speed_direction_v1/FeatureServer"
    )
    request_timeout: int = 50  # Timeout in seconds for each HTTP(s) request
    request_retries: int = 3  # Number of retries for each HTTP(s) request

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Loader for ESRI Elevation Data"""

from typing import Literal
from .._adapter_config import AdapterConfig


class LoadElevationData(AdapterConfig, frozen=True):
    """Config for LoadElevationData Adapter"""

    adapter_class: Literal["adapter.esri.LoadElevationData"] = (
        "adapter.esri.LoadElevationData"
    )
    image_server: str = (
        "https://elevation.arcgis.com/arcgis/rest/services/WorldElevation/Terrain/ImageServer"
    )
    image_size: list[int] = [4000, 4000]
    request_timeout: int = 50  # Timeout in seconds for each HTTP(s) request
    request_retries: int = 3  # Number of retries for each HTTP(s) request
    jpeg_quality: int = 99  # Quality of the JPEG image

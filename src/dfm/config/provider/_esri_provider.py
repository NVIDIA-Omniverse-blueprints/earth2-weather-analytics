# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""The default provider."""
from typing import Literal

from ._provider_config import ProviderConfig


class EsriProvider(ProviderConfig, frozen=True):
    """ESRI data provider."""

    provider_class: Literal["provider.EsriProvider"] = "provider.EsriProvider"
    server: str = "https://arcgis.com/"

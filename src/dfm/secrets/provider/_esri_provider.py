# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""ESRI provider secrets."""
from typing import Literal, Optional

from ._provider_secrets import ProviderSecrets


class EsriProvider(ProviderSecrets, frozen=True):
    """ESRI provider secrets."""

    provider_class: Literal["provider.EsriProvider"] = "provider.EsriProvider"
    api_key: Optional[str] = None
    user_name: Optional[str] = None
    password: Optional[str] = None

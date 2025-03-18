# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""The HRRR provider."""
from typing import Literal

from ._provider_config import ProviderConfig


class HrrrProvider(ProviderConfig, frozen=True):
    """HRRR data provider."""

    provider_class: Literal["provider.HrrrProvider"] = "provider.HrrrProvider"

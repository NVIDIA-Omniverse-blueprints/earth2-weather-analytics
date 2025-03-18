# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""HRRR provider secrets."""
from typing import Literal

from ._provider_secrets import ProviderSecrets


class HrrrProvider(ProviderSecrets, frozen=True):
    """HRRR provider secrets."""

    provider_class: Literal["provider.HrrrProvider"] = "provider.HrrrProvider"

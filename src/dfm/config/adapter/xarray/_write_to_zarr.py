# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""
This is the adapter config for the xarray WriteToZarr function.
"""
from typing import Literal

from .._adapter_config import AdapterConfig


class WriteToZarr(AdapterConfig, frozen=True):
    """
    This is the adapter config for the xarray WriteToZarr function.
    """

    adapter_class: Literal["adapter.xarray.WriteToZarr"] = "adapter.xarray.WriteToZarr"
    base_url: str

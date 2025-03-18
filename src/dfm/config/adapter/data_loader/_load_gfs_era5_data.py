# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Loader for GFS ERA5 data"""

from typing import Literal, Dict, Union, Optional

from .._adapter_config import AdapterConfig


class LoadGfsEra5Data(AdapterConfig, frozen=True):
    """Config for LoadGfsEra5Data Adapter"""

    adapter_class: Literal["adapter.data_loader.LoadGfsEra5Data"] = (
        "adapter.data_loader.LoadGfsEra5Data"
    )

    chunks: Union[Dict[str, int], int, Literal["auto"]]
    url: str
    engine_kwargs: Optional[Dict] = {}
    # offset in past days from today (positive int) for first available dataset
    # e.g. 10 = starting from 10 days ago from today
    offset_first: int
    offset_last: int  # offset from today (positive int) for the last available dataset
    frequency: int
    timeout: int = 180  # timeout for the internal download function

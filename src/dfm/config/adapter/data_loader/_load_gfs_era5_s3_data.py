# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Loader for GFS ERA5 data on S3"""

from typing import Literal, Dict, Optional, Union

from .._adapter_config import AdapterConfig


class LoadGfsEra5S3Data(AdapterConfig, frozen=True):
    """Config for LoadGfsEra5S3Data Adapter"""

    adapter_class: Literal["adapter.data_loader.LoadGfsEra5S3Data"] = (
        "adapter.data_loader.LoadGfsEra5S3Data"
    )

    chunks: Union[Dict[str, int], int, Literal["auto"]]
    bucket_name: str
    first_date: str
    last_date: str
    frequency: int
    tmp_download_folder: Optional[str] = None
    concurrency: Literal["async_proc_pool", "dask", "none"] = "async_proc_pool"
    num_processes: int = 4  # only for async proc pool
    read_timeout: int = 60
    connect_timeout: int = 120

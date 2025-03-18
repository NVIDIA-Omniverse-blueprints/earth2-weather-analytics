# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Loader for ECMWF ERA5 data"""

from typing import Optional, Literal, Dict, Union

from .._adapter_config import AdapterConfig


class LoadEcmwfEra5Data(AdapterConfig, frozen=True):
    """Config for LoadEcmwfEra5Data Adapter"""

    adapter_class: Literal["adapter.data_loader.LoadEcmwfEra5Data"] = (
        "adapter.data_loader.LoadEcmwfEra5Data"
    )

    engine: Optional[str] = "zarr"
    engine_kwargs: Optional[Dict] = {
        "consolidated": True,
        "storage_options": {"client_kwargs": {"timeout": 180}},
    }
    chunks: Union[Dict[str, int], int, Literal["auto"]]
    url: str
    first_date: str
    last_date: str
    frequency: int

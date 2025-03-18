# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Config Model for Fsspec"""
from typing import Dict, Any
from pydantic import BaseModel


class FsspecConf(BaseModel):
    """Used in provider and adapter configs to specify a Fsspec filesystem"""

    protocol: str
    storage_options: Dict[str, Any] = {}
    base_url: str

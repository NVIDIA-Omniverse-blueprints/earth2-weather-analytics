# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Base Class"""
from typing import Optional

from pydantic import BaseModel


class Dask(BaseModel, frozen=True):
    scheduler: str
    description: Optional[str] = None


class ResourceConfigs(BaseModel, frozen=True):
    """Base Class for all Runtime configs."""

    dask: Optional[Dask] = None

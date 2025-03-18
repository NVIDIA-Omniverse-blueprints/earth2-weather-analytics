# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Dict, Literal
from pydantic import UUID4
from ._field_advice import BranchFieldAdvice, SingleFieldAdvice
from ..response import ResponseBody


class DiscoveryResponse(ResponseBody, frozen=True):
    """Response object containing the discovery response for every
    node in the pipeline that was sent to discovery."""

    api_class: Literal["dfm.api.discovery.DiscoveryResponse"] = (
        "dfm.api.discovery.DiscoveryResponse"
    )
    advice: Dict[UUID4, BranchFieldAdvice | SingleFieldAdvice | None]

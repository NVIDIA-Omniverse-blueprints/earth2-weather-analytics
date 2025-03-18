# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""The base class for all Function models."""
from typing import Literal

from pydantic import ConfigDict
from ...common import PolymorphicBaseModel


class ResponseBody(PolymorphicBaseModel, frozen=True):
    """Abstract base class for the payload of Response objects."""

    model_config = ConfigDict(extra="forbid")

    api_class: Literal["ABSTRACT"]

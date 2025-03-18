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
from typing import Any, Dict, Literal, Tuple
from ...common import PolymorphicBaseModel


class ProviderSecrets(PolymorphicBaseModel, frozen=True):
    """Base Class for all Provider configs"""

    provider_class: Literal["ABSTRACT"]
    cache_storage_options: Dict[str, Any] = {}  # any secret storage_options, e.g. keys

    @classmethod
    def _discriminator_name(cls) -> str:
        return "provider_class"

    @classmethod
    def _rewrite_discriminator_value_to_model_class(
        cls, module_path: str, class_name: str
    ) -> Tuple[str, str]:
        return (f"dfm.secrets.{module_path}", class_name)

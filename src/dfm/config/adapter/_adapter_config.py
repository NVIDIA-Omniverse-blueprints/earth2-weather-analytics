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
from typing import Literal, Tuple
from ...common import PolymorphicBaseModel


class AdapterConfig(PolymorphicBaseModel, frozen=True):
    """The AdapterConfig follows the same 'logical name'
    idea to establish a 1-1 relation between a config model
    and the implementing class as the ProviderConfig. See
    there fore more details."""

    adapter_class: Literal["ABSTRACT"]

    @classmethod
    def _discriminator_name(cls) -> str:
        return "adapter_class"

    @classmethod
    def _rewrite_discriminator_value_to_model_class(
        cls, module_path: str, class_name: str
    ) -> Tuple[str, str]:
        return (f"dfm.config.{module_path}", class_name)

    def fully_qualified_adapter_class_name(self) -> str:
        """Returns the name of the implementing class"""
        return f"dfm.service.execute.{self.adapter_class}"

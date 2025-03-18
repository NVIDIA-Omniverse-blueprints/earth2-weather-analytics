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
from typing import Dict, Literal, Optional, Tuple
from ..adapter import AdapterConfig
from ...common import PolymorphicBaseModel
from ..common import FsspecConf


class ProviderConfig(PolymorphicBaseModel, frozen=True):
    """Base Class for all Provider configs.
    A config model (e.g. from yaml) is associated 1-1 with a provider (= the implementation)
    This 1-1 association is done like this:
    * the config model specifies a provider_class field with the "logical" name. The
      logical name is something like "provider.Dfm", i.e. the prefix of the path is abstracted
      away
    * This provider_class field is also used as the discriminator for Pydantic to parse
      and distinguish the correct polymorphic Provider types
    * The config model is found by prefixing the logical name with 'dfm.config.'
    * The implementation is found by prefixing the logical name with 'dfm.service.execute.'
    """

    provider_class: Literal["ABSTRACT"]
    description: Optional[str] = None
    # interface: maps "dfm.aip.*" function api_class to
    # either the class name of the implementing adapter (if the adapter doesn't require
    # a dedicated config model) or an AdapterConfig instance (if the adapter requires a
    # dedicated config model)
    interface: Dict[str, str | AdapterConfig] = {}
    cache_fsspec_conf: Optional[FsspecConf] = (
        None  # a place where adapters can store information
    )

    @classmethod
    def _discriminator_name(cls) -> str:
        return "provider_class"

    @classmethod
    def _rewrite_discriminator_value_to_model_class(
        cls, module_path: str, class_name: str
    ) -> Tuple[str, str]:
        return (f"dfm.config.{module_path}", class_name)

    def implementation_class(self) -> str:
        """Returns the name of the implementing class"""
        return f"dfm.service.execute.{self.provider_class}"

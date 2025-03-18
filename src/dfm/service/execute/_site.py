# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""This module contains the adapter registry"""

import importlib
from typing import Dict, List, Optional

from dfm.config import SiteConfig
from dfm.secrets import SiteSecrets
from dfm.api import FunctionCall
from dfm.service.common.request import DfmRequest

from dfm.service.common.exceptions import ServerError
from dfm.service.execute.resource import ResourceManager

# circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dfm.service.execute.provider import Provider, UninitializedAdapter
else:
    Provider = object
    UninitializedAdapter = object


class Site:
    """The Site essentially functions as a registry and factory for the different
    entities configured for this site (e.g. Providers and Adapters)"""

    def __init__(self, site_config: SiteConfig, site_secrets: Optional[SiteSecrets]):
        """prepares the site-wide registry."""
        self._config = site_config
        self._secrets = site_secrets or SiteSecrets()
        self._resources = ResourceManager(self, self._config.resources)
        self._provider_instances: Dict[str, Provider] = {}

    @property
    def config(self) -> SiteConfig:
        return self._config

    @property
    def secrets(self) -> SiteSecrets:
        return self._secrets

    @property
    def resources(self) -> ResourceManager:
        return self._resources

    def close(self):
        for provider in self._provider_instances.values():
            provider.close()

    def provider(self, provider: str) -> Provider:
        """Return provider instance from site-config. A provider with a given key is only
        instantiated once"""
        if provider in self._provider_instances:
            return self._provider_instances[provider]

        if provider not in self._config.providers:
            raise ServerError(f"Provider key {provider} not found in site config")

        provider_config = self._config.providers[provider]
        provider_secrets = self._secrets.providers.get(provider, None)

        try:
            module_path, class_name = provider_config.implementation_class().rsplit(
                ".", 1
            )  # type: ignore
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)
            provider_instance = provider_class(
                provider, self, provider_config, provider_secrets
            )
            self._provider_instances[provider] = provider_instance
            return provider_instance
        except Exception as ex:
            raise ServerError(ex) from ex

    def pre_instantiate_adapter(
        self, dfm_request: DfmRequest, func_params: FunctionCall
    ) -> UninitializedAdapter:
        provider = self.provider(func_params.provider)
        return provider.pre_instantiate_adapter(dfm_request, func_params)

    def pre_initialize_adapters_without_provider(
        self, dfm_request: DfmRequest, func_params: FunctionCall
    ) -> List[UninitializedAdapter]:
        results: List[UninitializedAdapter] = []
        for provider in self.config.providers:
            if func_params.api_class in self.config.providers[provider].interface:
                provider = self.provider(provider=provider)
                instance = provider.pre_instantiate_adapter(dfm_request, func_params)
                results.append(instance)
        return results

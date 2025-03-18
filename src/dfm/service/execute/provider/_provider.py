# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import importlib
from typing import Any, Dict, Generic, TypeVar
from dfm.config.common import FsspecConf
from dfm.service.common.request import DfmRequest
from dfm.api import FunctionCall
from dfm.config import ProviderConfig
from dfm.secrets.provider import ProviderSecrets
from dfm.service.execute import Site
from dfm.service.common.exceptions import ServerError

from dfm.service.common.logging import getLogger

ConfT = TypeVar("ConfT", bound=ProviderConfig)
SecretsT = TypeVar("SecretsT", bound=ProviderSecrets | None)

# For type checking only
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    # This import only happens during static type checking
    from ._uninitialized_adapter import UninitializedAdapter  # noqa: E402
else:
    # During runtime, UninitializedAdapter is just a placeholder
    UninitializedAdapter = object


class Provider(Generic[ConfT, SecretsT]):
    """
    A Provider is a provider of a function.
    """

    def __init__(self, provider: str, site: Site, config: ConfT, secrets: SecretsT):
        """
        Initialize the Provider.
        """
        self._provider = provider
        self._site = site
        self._config = config
        self._secrets = secrets
        self._logger = getLogger(f"{self.__class__.__name__}")

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def site(self) -> Site:
        return self._site

    @property
    def config(self) -> ConfT:
        return self._config

    @property
    def secrets(self) -> SecretsT:
        return self._secrets

    def close(self):
        pass

    def cache_fsspec_conf(self) -> FsspecConf | None:
        """
        Get the cache fsspec config.
        """
        if not self.config.cache_fsspec_conf:
            return None
        return FsspecConf(
            protocol=self.config.cache_fsspec_conf.protocol,
            storage_options=self._merged_storage_options(),
            base_url=self.config.cache_fsspec_conf.base_url,
        )

    def _merged_storage_options(self) -> Dict[str, Any]:
        """Merges the storage options from the config and the secrets"""
        config = (
            self.config.cache_fsspec_conf.storage_options
            if self.config.cache_fsspec_conf
            else {}
        )
        secrets = self.secrets.cache_storage_options if self.secrets is not None else {}
        return config | secrets

    def pre_instantiate_adapter(
        self, dfm_request: DfmRequest, func_params: FunctionCall
    ) -> UninitializedAdapter:
        """
        Pre-instantiate an adapter.
        """
        # need to import here again, because the TYPE_CHECKING trick above assigns
        # UninitalizedAdapter to object() and then we cannot call UninitializedAdapter()
        from ._uninitialized_adapter import UninitializedAdapter

        if func_params.api_class not in self._config.interface:
            raise ServerError(
                f"Function {func_params.api_class} is not in "
                f"provider {self._provider}'s interface"
            )
        adapter_config = self._config.interface[func_params.api_class]
        try:
            if isinstance(adapter_config, str):
                # the provider config either contains the implementation class name as a str
                adapter_impl = adapter_config
                adapter_config = None
            else:
                # or otherwise an adapter_config object.
                adapter_impl = adapter_config.fully_qualified_adapter_class_name()
                # adapter config stays as it is

            # create an instance by name
            module_path, class_name = adapter_impl.rsplit(".", 1)  # type: ignore
            module = importlib.import_module(module_path)
            adapter_class = getattr(module, class_name)
            adapter_instance = adapter_class.__new__(adapter_class)
            return UninitializedAdapter(
                dfm_request=dfm_request,
                adapter_instance=adapter_instance,
                provider=self,
                config=adapter_config,
                params=func_params,
            )
        except Exception as ex:
            raise ServerError(ex) from ex

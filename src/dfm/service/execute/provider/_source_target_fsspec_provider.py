# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict

import fsspec
from dfm.config.provider import (
    SourceTargetFsspecProvider as SourceTargetFsspecProviderConfig,
)
from dfm.secrets.provider import (
    SourceTargetFsspecProvider as SourceTargetFsspecProviderSecrets,
)
from dfm.service.execute import Site
from dfm.service.execute.provider import Provider


class SourceTargetFsspecProvider(
    Provider[SourceTargetFsspecProviderConfig, SourceTargetFsspecProviderSecrets | None]
):
    """
    A SourceTargetFsspecProvider is a provider that uses fsspec to access a source and target.
    """

    def __init__(
        self,
        provider: str,
        site: Site,
        config: SourceTargetFsspecProviderConfig,
        secrets: SourceTargetFsspecProviderSecrets | None,
    ):
        """
        Initialize the SourceTargetFsspecProvider.
        """
        super().__init__(provider, site, config, secrets)

    @property
    def protocol(self) -> str:
        return self.config.fsspec_conf.protocol

    @property
    def storage_options(self) -> Dict[str, Any]:
        """Merges the storage options from the config and the secrets"""
        secrets = self.secrets.storage_options if self.secrets else {}
        return self.config.fsspec_conf.storage_options | secrets

    def full_source_url(self, adapter_base: str, filename: str) -> str:
        return f"{self.config.fsspec_conf.base_url}/{adapter_base}/{filename}".replace(
            "//", "/"
        )

    def full_target_url(self, adapter_base: str, filename: str) -> str:
        return f"{self.config.target_base_url}/{adapter_base}/{filename}".replace(
            "//", "/"
        )

    def get_filesystem(self, asynchronous=False) -> Any:
        """
        Get a filesystem for the provider.
        """
        fs = fsspec.filesystem(
            protocol=self.protocol, asynchronous=asynchronous, **self.storage_options
        )
        return fs

    def get_mapper(self, full_url: str) -> fsspec.FSMap:
        """
        Get a mapper for the provider.
        """
        return self.get_filesystem().get_mapper(full_url)

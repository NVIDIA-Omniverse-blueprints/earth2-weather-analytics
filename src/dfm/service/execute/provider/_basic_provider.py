# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from dfm.config.provider import BasicProvider as BasicProviderConfig
from dfm.secrets.provider import BasicProvider as BasicProviderSecrets
from dfm.service.execute import Site
from dfm.service.execute.provider import Provider


class BasicProvider(Provider[BasicProviderConfig, BasicProviderSecrets | None]):
    """
    A BasicProvider is a provider that uses a basic provider config and secrets.
    """

    def __init__(
        self,
        provider: str,
        site: Site,
        config: BasicProviderConfig,
        secrets: BasicProviderSecrets | None,
    ):
        super().__init__(provider, site, config, secrets)

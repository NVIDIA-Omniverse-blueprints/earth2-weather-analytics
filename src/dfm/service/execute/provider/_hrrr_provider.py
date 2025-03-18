# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from dfm.config.provider import HrrrProvider as HrrrProviderConfig
from dfm.secrets.provider import HrrrProvider as HrrrProviderSecrets
from dfm.service.execute import Site
from dfm.service.execute.provider import Provider


class HrrrProvider(Provider[HrrrProviderConfig, HrrrProviderSecrets]):
    """
    Provider class for accessing HRRR (High-Resolution Rapid Refresh) weather data.

    This provider handles configuration and access to HRRR data, which is a NOAA weather
    model that provides high-resolution, frequently updated weather forecasts.

    Args:
        provider: The name/identifier of this provider instance
        site: The site configuration object
        config: Provider-specific configuration
        secrets: Provider-specific secrets/credentials
    """

    def __init__(
        self,
        provider: str,
        site: Site,
        config: HrrrProviderConfig,
        secrets: HrrrProviderSecrets,
    ):
        super().__init__(provider, site, config, secrets)

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from dfm.config.provider import EsriProvider as EsriProviderConfig
from dfm.secrets.provider import EsriProvider as EsriProviderSecrets
from dfm.service.execute import Site
from dfm.service.execute.provider import Provider


class EsriProvider(Provider[EsriProviderConfig, EsriProviderSecrets]):
    """
    Provider of elevation and wind data from ESRI.

    The provider requires access to the ArcGIS system, either via https://www.arcgis.com/
    or self-hosted ArcGIS Enterprise. Login details or an API Key are required to access the ArcGIS system.
    Please see the following for more information on how to create an API Key:
    https://developers.arcgis.com/documentation/security-and-authentication/api-key-authentication/tutorials/create-an-api-key/.

    The user credentials should be configured in ESRI Provider secrets.
    """

    def __init__(
        self,
        provider: str,
        site: Site,
        config: EsriProviderConfig,
        secrets: EsriProviderSecrets,
    ):
        super().__init__(provider, site, config, secrets)

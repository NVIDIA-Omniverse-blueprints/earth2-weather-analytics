# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from datetime import datetime, timezone
from typing import Any, Dict

import geojson

from arcgis.features import FeatureLayer

from dfm.api.dfm import GeoJsonFile
from dfm.api.esri import LoadUSWindForecastData as LoadUSWindForecastDataParams
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.esri import (
    LoadUSWindForecastData as LoadUSWindForecastDataConfig,
)
from dfm.service.common.logging._logging import shorten
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter
from dfm.service.execute.provider import Provider, EsriProvider
from ._common import get_gis, GeoJsonFileCachingIterator

LAYER_VALUES = {
    "national": 0,
    "regional": 1,
    "state": 2,
    "county": 3,
    "district": 4,
    "block_group": 5,
    "city": 6,
}


class LoadUSWindForecastData(
    NullaryAdapter[Provider, LoadUSWindForecastDataConfig, LoadUSWindForecastDataParams]
):
    """Adapter for loading US wind forecast data from ESRI services at various levels."""

    # The date format for the time filter
    DATE_FORMAT = "%Y-%m-%dT%H:%M"

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: EsriProvider,
        config: LoadUSWindForecastDataConfig,
        params: LoadUSWindForecastDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)
        self._gis = get_gis(self)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        # Check with ESRI what is the current timestamp available for the forecast
        layer = LAYER_VALUES[self.params.layer]
        wind_data = FeatureLayer(
            self.config.wind_forecast_server + f"/{layer}", gis=self._gis
        )
        timestamp = wind_data.properties.timeInfo.timeExtent[0]
        self._logger.info(
            "Current timestamp for ESRI wind forecast data is %s", timestamp
        )
        self.timestamp = timestamp
        return self._collect_local_hash_dict_helper(
            timestamp=timestamp,
            layer=self.params.layer,
            time_filter=self.params.time_filter,
            return_geojson=self.params.return_geojson,
            return_meta_data=self.params.return_meta_data,
        )

    def _instantiate_caching_iterator(self):
        cache_fsspec_conf = self.provider.cache_fsspec_conf()
        if cache_fsspec_conf:
            self._logger.info(
                "Instantiating caching iterator with cache_fsspec_conf: %s",
                cache_fsspec_conf,
            )
            return GeoJsonFileCachingIterator(self, cache_fsspec_conf)
        return None

    def body(self) -> Any:
        # Parse the time parameter
        self._logger.info(
            "LoadUSWindForecastData adapter using service %s",
            self.config.wind_forecast_server,
        )

        # Layers allow access to different levels of wind forecast data (national, regional, state, county, district, block group, city)
        layer = LAYER_VALUES[self.params.layer]
        wind_data = FeatureLayer(
            self.config.wind_forecast_server + f"/{layer}", gis=self._gis
        )

        query_params = {}
        if self.params.time_filter:
            time_filter = [
                datetime.strptime(self.params.time_filter[0], self.DATE_FORMAT),
                datetime.strptime(self.params.time_filter[1], self.DATE_FORMAT),
            ]
            query_params["time_filter"] = time_filter

        # Query the wind forecast data
        wind_features = wind_data.query(**query_params)
        wind_str = wind_features.to_json
        self._logger.info("wind_str: %s", shorten(wind_str))
        # Make sure we got proper geojson data by loading it to a geojson object
        wind_geojson = geojson.loads(wind_str)

        features = wind_geojson["features"]

        if len(features) == 0:
            raise ValueError("No data found in the wind forecast")

        # Get forecast start time
        timestamp = wind_data.properties.timeInfo.timeExtent[0]
        start_time = datetime.fromtimestamp(timestamp / 1000.0, timezone.utc)
        self.timestamp = timestamp

        # Prepare some metadata
        md = {
            "features": str(len(features)),
            "timestamp": start_time.strftime(self.DATE_FORMAT),
        }

        if self._caching_iterator:
            metadata_url = self._caching_iterator.write_file("metadata.json", md)
        else:
            metadata_url = None

        metadata = md if self.params.return_meta_data else None
        data = wind_str if self.params.return_geojson else None

        # if a cache is configured, write to it
        if self._caching_iterator:
            file_name = self._caching_iterator.get_cache_file_name()
            file_url = self._caching_iterator.write_file(file_name, wind_str)
        else:
            file_url = None

        # create the result object and return
        result = GeoJsonFile(
            metadata_url=metadata_url,
            url=file_url,
            timestamp=start_time.strftime(self.DATE_FORMAT),
            metadata=metadata,
            data=data,
        )
        self._logger.info("Returning geojson %s", shorten(result))

        return result

    async def prepare_to_send(
        self, result: GeoJsonFile
    ) -> ResponseBody:  # pylint: disable=arguments-renamed
        self._logger.info("prepare_to_send: result type: %s", type(result))
        return ValueResponse(value=result.model_dump())

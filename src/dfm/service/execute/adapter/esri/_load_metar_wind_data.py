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
from dfm.api.esri import LoadMetarWindData as LoadMetarWindDataParams
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.esri import LoadMetarWindData as LoadMetarWindDataConfig
from dfm.service.common.logging._logging import shorten
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter
from dfm.service.execute.provider import Provider, EsriProvider
from ._common import get_gis, GeoJsonFileCachingIterator

LAYER_VALUES = {"stations": 0, "buoys": 1}


def get_rounded_timestamp() -> int:
    """Get current timestamp rounded down to nearest 5 minutes."""
    now = datetime.now(timezone.utc)
    # Round down to nearest 5 minutes - ESRI updates the data every 5 minutes,
    # we can return a bit stale data for a few minutes.
    rounded = now.replace(minute=now.minute - (now.minute % 5), second=0, microsecond=0)
    return int(rounded.timestamp() * 1000)


class LoadMetarWindData(
    NullaryAdapter[Provider, LoadMetarWindDataConfig, LoadMetarWindDataParams]
):
    """Adapter for loading METAR observation data provided by weather stations and ocean buoys."""

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: EsriProvider,
        config: LoadMetarWindDataConfig,
        params: LoadMetarWindDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        self.timestamp = get_rounded_timestamp()
        return self._collect_local_hash_dict_helper(
            timestamp=self.timestamp,
            layer=LAYER_VALUES[self.params.layer],
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
        self._logger.info(
            "LoadMetarWindData adapter using service %s", self.config.metar_wind_server
        )

        # Access the FeatureService layer
        layer = LAYER_VALUES[self.params.layer]
        # Connect to the ArcGIS server
        self._gis = get_gis(self)
        # Get feature layer data from the ArcGIS server
        metar_data = FeatureLayer(
            self.config.metar_wind_server + f"/{layer}", gis=self._gis
        )
        # Query the METAR wind data (get all available data)
        metar_features = metar_data.query()
        metar_str = metar_features.to_json
        self._logger.info("metar_str: %s", shorten(metar_str))

        # Validate GeoJSON format
        metar_geojson = geojson.loads(metar_str)
        features = metar_geojson["features"]

        if len(features) == 0:
            raise ValueError("No data found in the METAR wind data")

        # Get current timestamp
        self.timestamp = get_rounded_timestamp()
        # Convert millisecond timestamp to datetime to easily stringify it
        current_time = datetime.fromtimestamp(self.timestamp / 1000, tz=timezone.utc)
        # Prepare metadata
        md = {
            "features": str(len(features)),
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M"),
            "layer": self.params.layer,
        }

        metadata = md if self.params.return_meta_data else None
        data = metar_str if self.params.return_geojson else None

        # Write to cache if configured
        if self._caching_iterator:
            metadata_url = self._caching_iterator.write_file("metadata.json", md)
            file_name = self._caching_iterator.get_cache_file_name()
            file_url = self._caching_iterator.write_file(file_name, metar_str)
        else:
            metadata_url = None
            file_url = None

        # Create and return result
        result = GeoJsonFile(
            metadata_url=metadata_url,
            url=file_url,
            timestamp=current_time.strftime("%Y-%m-%dT%H:%M"),
            metadata=metadata,
            data=data,
        )
        self._logger.info("Returning geojson %s", shorten(result))

        return result

    async def prepare_to_send(self, result: GeoJsonFile) -> ResponseBody:
        self._logger.info("prepare_to_send: result type: %s", type(result))
        return ValueResponse(value=result.model_dump())

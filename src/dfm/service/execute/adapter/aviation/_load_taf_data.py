# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to load TAF data from the FAA Aviation Weather Center."""

import json
from datetime import datetime, timezone
from typing import Any, Dict

import geojson
import requests

from dfm.api.aviation import LoadTafData as LoadTafDataParams
from dfm.api.dfm import GeoJsonFile
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.aviation import LoadTafData as LoadTafDataConfig
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter
from dfm.service.execute.provider import Provider


class LoadTafData(
    NullaryAdapter[Provider, LoadTafDataConfig, LoadTafDataParams]
):
    """Adapter for loading TAF (Terminal Aerodrome Forecast) data from AWC."""

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadTafDataConfig,
        params: LoadTafDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        rounded = now.replace(
            minute=now.minute - (now.minute % 10), second=0, microsecond=0
        )
        self._timestamp = int(rounded.timestamp() * 1000)
        return self._collect_local_hash_dict_helper(
            timestamp=self._timestamp,
            stations=self.params.stations,
        )

    def body(self) -> Any:
        self._logger.info("LoadTafData fetching from %s", self.config.awc_url)

        request_params = {"format": "json"}
        if self.params.stations:
            request_params["ids"] = ",".join(self.params.stations)

        response = requests.get(
            self.config.awc_url,
            params=request_params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        taf_list = response.json()

        if not isinstance(taf_list, list):
            taf_list = []

        self._logger.info("Received %d TAF reports", len(taf_list))

        features = []
        for taf in taf_list:
            lat = taf.get("lat")
            lon = taf.get("lon")
            if lat is None or lon is None:
                continue

            feature = geojson.Feature(
                geometry=geojson.Point((lon, lat)),
                properties={
                    "station_id": taf.get("icaoId", ""),
                    "lat": lat,
                    "lon": lon,
                    "issue_time": taf.get("issueTime", ""),
                    "valid_from": taf.get("validTimeFrom", ""),
                    "valid_to": taf.get("validTimeTo", ""),
                    "raw_text": taf.get("rawTAF", ""),
                    "forecast_groups": taf.get("fcsts", []),
                },
            )
            features.append(feature)

        fc = geojson.FeatureCollection(features)
        taf_str = geojson.dumps(fc)

        current_time = datetime.now(timezone.utc)
        md = {
            "features": str(len(features)),
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M"),
            "source": "AWC",
        }

        metadata = md if self.params.return_meta_data else None
        data = taf_str if self.params.return_geojson else None

        metadata_url = None
        file_url = None
        if self._caching_iterator:
            metadata_url = self._caching_iterator.write_file("metadata.json", md)
            file_name = self._caching_iterator.get_cache_file_name()
            file_url = self._caching_iterator.write_file(file_name, taf_str)

        result = GeoJsonFile(
            metadata_url=metadata_url,
            url=file_url,
            timestamp=current_time.strftime("%Y-%m-%dT%H:%M"),
            metadata=metadata,
            data=data,
        )
        return result

    async def prepare_to_send(self, result: GeoJsonFile) -> ResponseBody:
        return ValueResponse(value=result.model_dump())

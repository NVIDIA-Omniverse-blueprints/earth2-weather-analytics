# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to load full METAR data from the FAA Aviation Weather Center."""

import json
from datetime import datetime, timezone
from typing import Any, Dict

import geojson
import requests

from dfm.api.aviation import LoadMetarData as LoadMetarDataParams
from dfm.api.dfm import GeoJsonFile
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.aviation import LoadMetarData as LoadMetarDataConfig
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter
from dfm.service.execute.provider import Provider


# Flight category thresholds
def _classify_flight_category(visibility_sm, ceiling_ft):
    """Classify flight category per FAA standards."""
    try:
        ceiling_ft = float(ceiling_ft) if ceiling_ft is not None else 99999
    except (ValueError, TypeError):
        ceiling_ft = 99999
    try:
        visibility_sm = float(visibility_sm) if visibility_sm is not None else 10
    except (ValueError, TypeError):
        visibility_sm = 10

    if visibility_sm < 1 or ceiling_ft < 500:
        return "LIFR"
    elif visibility_sm < 3 or ceiling_ft < 1000:
        return "IFR"
    elif visibility_sm <= 5 or ceiling_ft <= 3000:
        return "MVFR"
    else:
        return "VFR"


class LoadMetarData(
    NullaryAdapter[Provider, LoadMetarDataConfig, LoadMetarDataParams]
):
    """Adapter for loading full METAR observations from the AWC API."""

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadMetarDataConfig,
        params: LoadMetarDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        # Round to 5 minutes for caching
        now = datetime.now(timezone.utc)
        rounded = now.replace(
            minute=now.minute - (now.minute % 5), second=0, microsecond=0
        )
        self._timestamp = int(rounded.timestamp() * 1000)
        return self._collect_local_hash_dict_helper(
            timestamp=self._timestamp,
            stations=self.params.stations,
            bbox=self.params.bbox,
        )

    def body(self) -> Any:
        self._logger.info("LoadMetarData fetching from %s", self.config.awc_url)

        # Build request params
        request_params = {"format": "json"}
        if self.params.stations:
            request_params["ids"] = ",".join(self.params.stations)
        if self.params.bbox:
            request_params["bbox"] = self.params.bbox

        # Fetch from AWC API
        response = requests.get(
            self.config.awc_url,
            params=request_params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        metar_list = response.json()

        if not isinstance(metar_list, list):
            metar_list = []

        self._logger.info("Received %d METAR reports", len(metar_list))

        # Convert to GeoJSON FeatureCollection
        features = []
        for obs in metar_list:
            lat = obs.get("lat")
            lon = obs.get("lon")
            if lat is None or lon is None:
                continue

            # Extract ceiling from cloud layers
            ceiling_ft = None
            clouds = obs.get("clouds", [])
            for cloud in clouds:
                cover = cloud.get("cover", "")
                base = cloud.get("base")
                if cover in ("BKN", "OVC", "VV") and base is not None:
                    if ceiling_ft is None or base < ceiling_ft:
                        ceiling_ft = base

            visibility = obs.get("visib")
            flight_cat = obs.get(
                "fltcat",
                _classify_flight_category(visibility, ceiling_ft),
            )

            feature = geojson.Feature(
                geometry=geojson.Point((lon, lat)),
                properties={
                    "station_id": obs.get("icaoId", obs.get("stationId", "")),
                    "lat": lat,
                    "lon": lon,
                    "temp_c": obs.get("temp"),
                    "dewpoint_c": obs.get("dewp"),
                    "wind_dir": obs.get("wdir"),
                    "wind_speed_kts": obs.get("wspd"),
                    "wind_gust_kts": obs.get("wgst"),
                    "visibility_sm": visibility,
                    "ceiling_ft": ceiling_ft,
                    "altimeter_inhg": obs.get("altim"),
                    "flight_category": flight_cat,
                    "raw_text": obs.get("rawOb", ""),
                    "observation_time": obs.get("reportTime", obs.get("obsTime", "")),
                },
            )
            features.append(feature)

        fc = geojson.FeatureCollection(features)
        metar_str = geojson.dumps(fc)

        current_time = datetime.now(timezone.utc)
        md = {
            "features": str(len(features)),
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M"),
            "source": "AWC",
        }

        metadata = md if self.params.return_meta_data else None
        data = metar_str if self.params.return_geojson else None

        # Cache if available
        metadata_url = None
        file_url = None
        if self._caching_iterator:
            metadata_url = self._caching_iterator.write_file("metadata.json", md)
            file_name = self._caching_iterator.get_cache_file_name()
            file_url = self._caching_iterator.write_file(file_name, metar_str)

        result = GeoJsonFile(
            metadata_url=metadata_url,
            url=file_url,
            timestamp=current_time.strftime("%Y-%m-%dT%H:%M"),
            metadata=metadata,
            data=data,
        )
        self._logger.info("Returning METAR GeoJSON with %d features", len(features))
        return result

    async def prepare_to_send(self, result: GeoJsonFile) -> ResponseBody:
        return ValueResponse(value=result.model_dump())

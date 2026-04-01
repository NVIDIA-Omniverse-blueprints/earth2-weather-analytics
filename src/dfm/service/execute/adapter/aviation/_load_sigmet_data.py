# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to load SIGMET/AIRMET data from the FAA Aviation Weather Center."""

from datetime import datetime, timezone
from typing import Any, Dict

import geojson
import requests

from dfm.api.aviation import LoadSigmetData as LoadSigmetDataParams
from dfm.api.dfm import GeoJsonFile
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.aviation import LoadSigmetData as LoadSigmetDataConfig
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter
from dfm.service.execute.provider import Provider


class LoadSigmetData(
    NullaryAdapter[Provider, LoadSigmetDataConfig, LoadSigmetDataParams]
):
    """Adapter for loading SIGMET/AIRMET advisories from the AWC API."""

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadSigmetDataConfig,
        params: LoadSigmetDataParams,
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
            hazard_type=self.params.hazard_type,
        )

    def body(self) -> Any:
        self._logger.info(
            "LoadSigmetData fetching %s from %s",
            self.params.hazard_type,
            self.config.awc_url,
        )

        request_params = {
            "format": "json",
            "type": self.params.hazard_type,
        }

        response = requests.get(
            self.config.awc_url,
            params=request_params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        advisory_list = response.json()

        if not isinstance(advisory_list, list):
            advisory_list = []

        self._logger.info(
            "Received %d %s advisories", len(advisory_list), self.params.hazard_type
        )

        features = []
        for adv in advisory_list:
            # Build geometry from coordinates
            raw_coords = adv.get("coords", [])

            # Normalize coords - AWC returns [{"lat":..,"lon":..},...] dicts
            coords = []
            for c in raw_coords:
                if isinstance(c, dict):
                    coords.append((float(c.get("lon", 0)), float(c.get("lat", 0))))
                elif isinstance(c, (list, tuple)) and len(c) >= 2:
                    coords.append((float(c[0]), float(c[1])))

            if not coords:
                lats = adv.get("lats", [])
                lons = adv.get("lons", [])
                if lats and lons:
                    coords = [(float(lo), float(la)) for lo, la in zip(lons, lats)]

            if len(coords) >= 3:
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geometry = geojson.Polygon([coords])
            elif len(coords) == 1:
                geometry = geojson.Point(coords[0])
            else:
                continue

            feature = geojson.Feature(
                geometry=geometry,
                properties={
                    "advisory_type": self.params.hazard_type.upper(),
                    "hazard": adv.get("hazard", ""),
                    "severity": adv.get("severity", ""),
                    "valid_from": adv.get("validTimeFrom", ""),
                    "valid_to": adv.get("validTimeTo", ""),
                    "altitude_low_ft": adv.get("altLow"),
                    "altitude_high_ft": adv.get("altHi"),
                    "raw_text": adv.get("rawAirSigmet", adv.get("rawText", "")),
                },
            )
            features.append(feature)

        fc = geojson.FeatureCollection(features)
        sigmet_str = geojson.dumps(fc)

        current_time = datetime.now(timezone.utc)
        md = {
            "features": str(len(features)),
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M"),
            "source": "AWC",
            "type": self.params.hazard_type,
        }

        metadata = md if self.params.return_meta_data else None
        data = sigmet_str if self.params.return_geojson else None

        metadata_url = None
        file_url = None
        if self._caching_iterator:
            metadata_url = self._caching_iterator.write_file("metadata.json", md)
            file_name = self._caching_iterator.get_cache_file_name()
            file_url = self._caching_iterator.write_file(file_name, sigmet_str)

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

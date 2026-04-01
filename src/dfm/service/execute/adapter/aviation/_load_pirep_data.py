# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to load PIREP data from the FAA Aviation Weather Center."""

from datetime import datetime, timezone
from typing import Any, Dict

import geojson
import requests

from dfm.api.aviation import LoadPirepData as LoadPirepDataParams
from dfm.api.dfm import GeoJsonFile
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.aviation import LoadPirepData as LoadPirepDataConfig
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter
from dfm.service.execute.provider import Provider


class LoadPirepData(
    NullaryAdapter[Provider, LoadPirepDataConfig, LoadPirepDataParams]
):
    """Adapter for loading Pilot Reports from the AWC API."""

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadPirepDataConfig,
        params: LoadPirepDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        rounded = now.replace(
            minute=now.minute - (now.minute % 5), second=0, microsecond=0
        )
        self._timestamp = int(rounded.timestamp() * 1000)
        return self._collect_local_hash_dict_helper(
            timestamp=self._timestamp,
            bbox=self.params.bbox,
            age_hours=self.params.age_hours,
        )

    def body(self) -> Any:
        self._logger.info("LoadPirepData fetching from %s", self.config.awc_url)

        request_params = {
            "format": "json",
            "age": str(self.params.age_hours),
            "type": "pirep",
        }
        if self.params.bbox:
            request_params["bbox"] = self.params.bbox

        response = requests.get(
            self.config.awc_url,
            params=request_params,
            timeout=self.config.request_timeout,
        )
        response.raise_for_status()
        pirep_list = response.json()

        if not isinstance(pirep_list, list):
            pirep_list = []

        self._logger.info("Received %d PIREPs", len(pirep_list))

        features = []
        for pirep in pirep_list:
            lat = pirep.get("lat")
            lon = pirep.get("lon")
            if lat is None or lon is None:
                continue

            # Extract turbulence and icing info
            turb_type = None
            turb_intensity = None
            ice_type = None
            ice_intensity = None

            turb_conds = pirep.get("turbulence", [])
            if turb_conds:
                turb = turb_conds[0]
                turb_type = turb.get("type", "")
                turb_intensity = turb.get("intensity", "")

            ice_conds = pirep.get("icing", [])
            if ice_conds:
                ice = ice_conds[0]
                ice_type = ice.get("type", "")
                ice_intensity = ice.get("intensity", "")

            feature = geojson.Feature(
                geometry=geojson.Point((lon, lat)),
                properties={
                    "report_type": pirep.get("reportType", "PIREP"),
                    "lat": lat,
                    "lon": lon,
                    "altitude_ft": pirep.get("fltlvl", pirep.get("alt")),
                    "aircraft_type": pirep.get("acType", ""),
                    "observation_time": pirep.get("obsTime", ""),
                    "turbulence_type": turb_type,
                    "turbulence_intensity": turb_intensity,
                    "icing_type": ice_type,
                    "icing_intensity": ice_intensity,
                    "sky_condition": pirep.get("skyCond", ""),
                    "weather": pirep.get("wx", ""),
                    "temperature_c": pirep.get("temp"),
                    "wind_dir": pirep.get("wdir"),
                    "wind_speed_kts": pirep.get("wspd"),
                    "raw_text": pirep.get("rawOb", ""),
                },
            )
            features.append(feature)

        fc = geojson.FeatureCollection(features)
        pirep_str = geojson.dumps(fc)

        current_time = datetime.now(timezone.utc)
        md = {
            "features": str(len(features)),
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M"),
            "source": "AWC",
            "age_hours": self.params.age_hours,
        }

        metadata = md if self.params.return_meta_data else None
        data = pirep_str if self.params.return_geojson else None

        metadata_url = None
        file_url = None
        if self._caching_iterator:
            metadata_url = self._caching_iterator.write_file("metadata.json", md)
            file_name = self._caching_iterator.get_cache_file_name()
            file_url = self._caching_iterator.write_file(file_name, pirep_str)

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

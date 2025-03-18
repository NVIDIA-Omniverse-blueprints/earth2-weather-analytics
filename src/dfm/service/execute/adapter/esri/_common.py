#! /usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from arcgis import GIS
import os
import json
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from dfm.api.dfm import GeoJsonFile
from dfm.service.execute.adapter import CachingIterator
from dfm.service.common.logging._logging import shorten


def get_gis(adapter):
    """Get the GIS object for the adapter."""
    if adapter.provider.secrets:
        if adapter.provider.secrets.api_key:
            adapter._logger.info("Using API key from provider secrets")
            return GIS(api_key=adapter.provider.secrets.api_key)
        elif adapter.provider.secrets.user_name and adapter.provider.secrets.password:
            adapter._logger.info("Using user name and password from provider secrets")
            return GIS(
                username=adapter.provider.secrets.user_name,
                password=adapter.provider.secrets.password,
            )
    # Try env variable for testing purposes
    api_key = os.environ.get("DFM_ESRI_API_KEY", None)
    if api_key:
        adapter._logger.info("Using API key from environment variable DFM_ESRI_API_KEY")
        return GIS(api_key=api_key)
    adapter._logger.warning(
        "No API key or user name and password provided, adapter might not function properly"
    )
    return GIS()


class GeoJsonFileCachingIterator(CachingIterator):
    """Common caching iterator for GeoJSON data from ESRI services."""

    def get_cache_file_name(self):
        """Generate a cache file name based on adapter parameters."""
        p = self.adapter.params
        base = f"{self.adapter.timestamp}_{p.layer}"

        # Handle time filter if present
        if hasattr(p, "time_filter") and p.time_filter:
            base += f"_{p.time_filter[0]}_{p.time_filter[1]}"

        return base.replace(":", "-").replace(".", "-") + ".json"

    async def write_value_to_cache(self, element_counter: int, item: Any):
        """Write the value to the cache."""
        # the adapter calls explicit write in the body (for now),
        # so no need to write anything in the stream
        pass

    def write_file(self, filename: str, contents: str | JsonValue) -> str:
        """Write the file to the cache."""
        path = f"{self.full_cache_folder_path}/{filename}"
        fs = self.filesystem
        as_str = (
            contents if isinstance(contents, str) else json.dumps(contents, indent=4)
        )
        as_bytes = as_str.encode("utf-8")
        fs.pipe(path, as_bytes)
        self._logger.info("Wrote file %s", path)
        return path

    async def load_values_from_cache(
        self, _expected_num_elements: int
    ) -> list[Any] | None:
        """Load the values from the cache."""
        self._logger.info("Loading values from cache %s", self.full_cache_folder_path)
        fs = self.filesystem
        cache_folder = Path(self.full_cache_folder_path)
        metadata_file = cache_folder.joinpath("metadata.json").as_posix()
        if fs.exists(metadata_file) and self.adapter.params.return_meta_data:
            self._logger.info("Loading metadata from cache %s", metadata_file)
            metadata_url = metadata_file
            with fs.open(metadata_file) as f:
                as_bytes = f.read()
                metadata = json.loads(as_bytes.decode("utf-8"))
        else:
            metadata_url = None
            metadata = None

        result_file = cache_folder.joinpath(self.get_cache_file_name()).as_posix()
        self._logger.info("Checking if geojson file exists in cache %s", result_file)
        if fs.exists(result_file) and self.adapter.params.return_geojson:
            self._logger.info("Loading geojson from cache %s", result_file)
            with fs.open(result_file, "rb") as f:
                as_bytes = f.read()
                geojson_str = as_bytes.decode("utf-8")
        else:
            geojson_str = None

        result = GeoJsonFile(
            metadata_url=metadata_url,
            url=result_file,
            timestamp=metadata["timestamp"] if metadata else "",
            metadata=metadata,
            data=geojson_str,
        )
        self._logger.info("Returning geojson %s", shorten(result))
        # Caching iterator expects a list of values
        return [result]

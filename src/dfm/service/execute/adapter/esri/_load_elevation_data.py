# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# Standard library imports
import asyncio
import base64
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

# Third-party imports
import aiohttp
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field, HttpUrl, JsonValue

from arcgis.raster import ImageryLayer
from arcgis.raster.functions import apply as apply_raster_function

# Local imports
from dfm.api.dfm import TextureFile
from dfm.api.esri import LoadElevationData as LoadElevationDataParams
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.config.adapter.esri import LoadElevationData as LoadElevationDataConfig
from dfm.service.common.logging._logging import shorten
from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter import NullaryAdapter, CachingIterator
from dfm.service.execute.provider import Provider, EsriProvider

from ._common import get_gis

PROCESSING_TO_RASTER_FUNCTION = {
    "none": None,
    "hillshade": "Hillshade",
    "multi_directional_hillshade": "Multi-Directional_Hillshade",
    "elevation_tinted_hillshade": "Elevation_Tinted_Hillshade",
    "ellipsoidal_height": "Ellipsoidal_Height",
    "slope_degrees_map": "Slope_Degrees_Map",
    "aspect_map": "Aspect_Map",
}


class SpatialReference(BaseModel):
    """Spatial reference system identifiers."""

    wkid: int
    latest_wkid: int = Field(alias="latestWkid")


class MapExtent(BaseModel):
    """Geographic extent of the map."""

    xmin: float
    ymin: float
    xmax: float
    ymax: float
    spatial_reference: SpatialReference = Field(alias="spatialReference")


class ElevationMapImage(BaseModel):
    """Represents an elevation map image response from ESRI services."""

    href: HttpUrl
    width: int
    height: int
    extent: MapExtent
    scale: float = 0


class ElevationMapImageCachingIterator(CachingIterator):
    """Caching iterator for elevation map images."""

    def get_cache_file_name(self):
        """Get the cache file name for the elevation map image."""
        p = self.adapter.params
        proj = str(p.wkid)
        base = f"{p.lon_minmax[0]:.2f}_{p.lat_minmax[0]:.2f}_{p.lon_minmax[1]:.2f}_{p.lat_minmax[1]:.2f}_{proj}_{p.processing}_{proj}"
        return base.replace(".", "-") + "." + p.texture_format.lower()

    async def write_value_to_cache(self, element_counter: int, item: Any):
        """Write the value to the cache."""
        # the adapter calls explicit write in the body (for now),
        # so no need to write anything in the stream
        pass

    def write_file(self, filename: str, contents: bytes | JsonValue) -> str:
        """Write the file to the cache."""
        path = f"{self.full_cache_folder_path}/{filename}"
        fs = self.filesystem
        as_bytes = (
            contents
            if isinstance(contents, bytes)
            else json.dumps(contents, indent=4).encode("utf-8")
        )
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
            with fs.open(metadata_file, mode="r") as f:
                as_str = f.read()
                metadata = json.loads(as_str)
        else:
            metadata_url = None
            metadata = None

        result_file = cache_folder.joinpath(self.get_cache_file_name()).as_posix()
        self._logger.info("Checking if image file exists in cache %s", result_file)
        if fs.exists(result_file) and self.adapter.params.return_image_data:
            self._logger.info("Loading image from cache %s", result_file)
            with fs.open(result_file) as f:
                img_bytes = f.read()
                img_str = base64.b64encode(img_bytes).decode()
        else:
            img_str = None

        result = TextureFile(
            metadata_url=metadata_url,
            url=result_file,
            format=self.adapter.params.texture_format,
            timestamp=metadata["timestamp"] if metadata else "",
            metadata=metadata,
            base64_image_data=img_str,
        )
        self._logger.info("Returning texture %s", shorten(result))
        # Caching iterator expects a list of values
        return [result]


class LoadElevationData(
    NullaryAdapter[Provider, LoadElevationDataConfig, LoadElevationDataParams]
):
    """Adapter for loading elevation data from ESRI services."""

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: EsriProvider,
        config: LoadElevationDataConfig,
        params: LoadElevationDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        """Collect the local hash dictionary."""
        return self._collect_local_hash_dict_helper(
            lon_minmax=self.params.lon_minmax,
            lat_minmax=self.params.lat_minmax,
            wkid=self.params.wkid,
            processing=self.params.processing,
            output=self.params.output,
            texture_format=self.params.texture_format,
        )

    def _instantiate_caching_iterator(self):
        """Instantiate the caching iterator."""
        cache_fsspec_conf = self.provider.cache_fsspec_conf()
        self._logger.debug("Cache fsspec config: %s", cache_fsspec_conf)
        self._logger.info(
            "Instantiating caching iterator with cache_fsspec_conf: %s",
            cache_fsspec_conf,
        )
        return ElevationMapImageCachingIterator(self, cache_fsspec_conf)

    async def download_file(self, url):
        """Download the file from the URL."""
        url = str(url)
        self._logger.info("Downloading %s", url)
        for retry in range(self.config.request_retries):
            buffer = io.BytesIO()
            try:
                async with aiohttp.ClientSession() as session:
                    async with asyncio.timeout(self.config.request_timeout):
                        async with session.get(url) as resp:
                            resp.raise_for_status()
                            async for chunk in resp.content.iter_chunked(8192):
                                buffer.write(chunk)
                self._logger.info("Downloaded %s", url)
                return buffer
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                self._logger.error("Download failed: %s", e)
                if retry < self.config.request_retries:
                    self._logger.info(
                        "Retrying download %d of %d for %s",
                        retry + 1,
                        self.config.request_retries,
                        url,
                    )
                else:
                    self._logger.error(
                        "Failed to download %s after %d retries",
                        url,
                        self.config.request_retries,
                    )
                    return None

    def _adjust_image_size(self, xmin, ymin, xmax, ymax, wkid, desired_width):
        """
        Calculates image dimensions (width, height) for a raster export, ensuring
        square pixels (i.e. the same map units per pixel in both directions) while
        maintaining the aspect ratio of the given bounding box.

        Parameters:
        xmin, ymin, xmax, ymax: Bounding box coordinates.
        wkid: Spatial reference system of input bounding box.
        desired_width: Desired image width in pixels.

        Returns:
        A tuple (width, height) in pixels.
        """
        # Compute geographic width and height of the bounding box
        geo_width = xmax - xmin
        geo_height = ymax - ymin
        # Compute the bounding box aspect ratio (width / height)
        aspect_ratio = geo_width / geo_height

        image_width = desired_width
        image_height = desired_width / aspect_ratio

        return int(round(image_width)), int(round(image_height))

    def _remove_transparent_stripes(self, buffer: io.BytesIO) -> io.BytesIO:
        """Remove transparent stripes from the top and bottom of a PNG image.

        Args:
            buffer (io.BytesIO): Input PNG image buffer

        Returns:
            io.BytesIO: New buffer with the image cropped to remove transparent stripes,
                       converted to JPEG if specified in params.texture_format
        """
        # Open the image
        img = Image.open(buffer)

        # Ensure we're working with RGBA mode
        if img.mode != "RGBA":
            raise RuntimeError(
                "Something unexpected happened, image is not in RGBA mode"
            )

        # Convert to numpy array for analysis
        img_array = np.array(img)

        # Get alpha channel (transparency)
        alpha = img_array[:, :, 3]

        # Function to check if a row is transparent
        def is_transparent_row(row_idx):
            return np.all(
                alpha[row_idx] == 0
            )  # All pixels in row are fully transparent

        height = img_array.shape[0]

        # Find the first non-transparent row from top
        top = 0
        for i in range(height):
            if not is_transparent_row(i):
                top = i
                break

        # Find the first non-transparent row from bottom
        bottom = height
        for i in range(height - 1, -1, -1):
            if not is_transparent_row(i):
                bottom = i + 1
                break

        self._logger.info(
            f"Detected transparent stripes - top: {top}, bottom: {bottom} (original height: {height})"
        )

        if top >= bottom:
            self._logger.warning(
                "Invalid crop bounds detected, returning original image"
            )
            buffer.seek(0)
            return buffer

        # Crop the image
        cropped = img.crop((0, top, img.width, bottom))

        # Save to new buffer
        output = io.BytesIO()

        # Convert to JPEG if requested
        if self.params.texture_format.upper() in ["JPG", "JPEG"]:
            # Convert to RGB with white background
            background = Image.new("RGB", cropped.size, (255, 255, 255))
            background.paste(
                cropped, mask=cropped.split()[3]
            )  # Use alpha channel as mask
            background.save(output, format="JPEG", quality=self.config.jpeg_quality)
        else:
            cropped.save(output, format="PNG")

        output.seek(0)
        return output

    def body(self) -> Any:
        async def async_body() -> Any:
            # Parse the time parameter
            self._logger.info(
                "LoadElevationData adapter using service %s", self.config.image_server
            )

            # Access the ImageService
            imagery_layer = ImageryLayer(self.config.image_server, gis=get_gis(self))

            # Apply the post-processing server-side function if provided
            if self.params.processing:
                raster_function = PROCESSING_TO_RASTER_FUNCTION[self.params.processing]
                imagery_layer = apply_raster_function(imagery_layer, raster_function)

            # Use the image size from the params if provided, otherwise use the default size from the config
            image_size = (
                self.params.image_size
                if self.params.image_size
                else self.config.image_size
            )

            # region = self._adjust_coordinates()
            xmin = min(self.params.lon_minmax)
            xmax = max(self.params.lon_minmax)
            ymin = min(self.params.lat_minmax)
            ymax = max(self.params.lat_minmax)
            wkid = self.params.wkid

            width, height = self._adjust_image_size(
                xmin, ymin, xmax, ymax, wkid, image_size[0]
            )
            self._logger.info("Adjusted image size to %d x %d", width, height)

            bbox = {
                "xmin": xmin,
                "ymin": ymin,
                "xmax": xmax,
                "ymax": ymax,
                "spatialReference": {"wkid": wkid},
            }

            d = imagery_layer.export_image(
                bbox=bbox,
                size=(width, height),
                image_sr=bbox[
                    "spatialReference"
                ],  # Use the same spatial reference as the bounding box
                export_format="png32",  # Use png32 for now, we'll convert to jpeg if requested.
                f="json",  # Get metadata first, download the image later
            )

            meta = ElevationMapImage.model_validate(d)
            self._logger.info("Received metadata %s", meta)
            # Now download the image
            buffer = await self.download_file(meta.href)

            if not buffer:
                raise ValueError("Failed to download image")

            # Remove transparent stripes from the image
            buffer = self._remove_transparent_stripes(buffer)
            img_bytes = buffer.getvalue()

            # Compute the metadata
            # Get the current time in UTC and use it as the timestamp
            current_time_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
            md = {  # write lon and lat info
                "lon_minmax": [xmin, xmax],
                "lat_minmax": [ymin, ymax],
                "width": width,
                "height": height,
                "timestamp": current_time_utc,
                "wkid": wkid,
            }

            metadata = md if self.params.return_meta_data else None

            # in case we want to send it back to the client
            img_str = (
                base64.b64encode(img_bytes).decode()
                if self.params.return_image_data
                else None
            )

            # if a cache is configured, write to it
            metadata_url = None
            file_url = None
            if self._caching_iterator:
                metadata_url = self._caching_iterator.write_file("metadata.json", md)
                file_name = self._caching_iterator.get_cache_file_name()
                file_url = self._caching_iterator.write_file(file_name, img_bytes)

            # create the result object and return
            result = TextureFile(
                metadata_url=metadata_url,
                url=file_url,
                format=self.params.texture_format,
                timestamp=current_time_utc,
                metadata=metadata,
                base64_image_data=img_str,
            )
            self._logger.info("Returning texture %s", shorten(result))
            return result

        return async_body()

    async def prepare_to_send(
        self, result: TextureFile
    ) -> ResponseBody:  # pylint: disable=arguments-renamed
        self._logger.info("prepare_to_send: result type: %s", type(result))
        return ValueResponse(value=result.model_dump())

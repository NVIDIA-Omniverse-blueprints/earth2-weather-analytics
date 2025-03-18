# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""DfmFunction to load ESRI Elevation Data"""

from typing import Literal, Optional
from dfm.api import FunctionCall


class LoadElevationData(FunctionCall, frozen=True):
    """
    Function to load elevation data from ESRI's terrain service with optional processing
    and visualization options.

    Args:
        lat_minmax (list[float]): List of [min_latitude, max_latitude] defining the latitude bounds
            of the area to load. Values should be in degrees in WGS84 or meters in Web Mercator,
            depending on the specified WKID.
        lon_minmax (list[float]): List of [min_longitude, max_longitude] defining the longitude bounds
            of the area to load. Values should be in degrees in WGS84 or meters in Web Mercator,
            depending on the specified WKID.
        wkid (Literal[3857, 4326]): Well-known ID of the spatial reference system. Controls both the
            input coordinate system and the output projection. Options:
            - 4326: WGS84 geographic coordinates in degrees (default)
            - 3857: Web Mercator projection in meters
        output (Literal["texture"]): Output format for the elevation data. Currently
            only "texture" is supported.
        processing (Literal): Type of terrain analysis to apply to the elevation data. Options:
            - "none": Raw elevation data without processing
            - "hillshade": Standard hillshade visualization with default parameters
            - "multi_directional_hillshade": Enhanced hillshade from multiple light angles
            - "elevation_tinted_hillshade": Hillshade colored by elevation values
            - "ellipsoidal_height": Height above WGS84 ellipsoid
            - "slope_degrees_map": Slope steepness in degrees
            - "aspect_map": Slope direction (aspect) visualization
        image_size (Optional[list[int]]): Size of the output image as [width, height].
            If not provided, uses adapter config default. Image hight can be adjusted
            by the adapter to maintain the aspect ratio of the input region.
        return_image_data (bool): If True, includes base64-encoded image data in response.
            Default is False.
        return_meta_data (bool): If True, includes metadata in response. Default is False.
        texture_format (Literal["png", "jpeg"]): Format of the output texture. Options:
            - "png": Supports transparency, lossless compression (default)
            - "jpeg": Better compression, smaller file size, no transparency

    Returns:
        TextureFile: A container with the following fields:
            - url: URL to the cached texture file
            - metadata_url: URL to the metadata file (if return_meta_data is True)
            - base64_image_data: Base64-encoded image data (if return_image_data is True)
            - metadata: Dictionary containing:
                - lon_minmax: [min_longitude, max_longitude]
                - lat_minmax: [min_latitude, max_latitude]
                - width: Image width in pixels
                - height: Image height in pixels
                - wkid: Spatial reference system ID
            - format: Texture format ("png" or "jpeg")
            - timestamp: Timestamp of the data
    """

    api_class: Literal["dfm.api.esri.LoadElevationData"] = (
        "dfm.api.esri.LoadElevationData"
    )
    # Latitude bounds [min_lat, max_lat] in degrees (WGS84) or meters (Web Mercator)
    lat_minmax: list[float]
    # Longitude bounds [min_lon, max_lon] in degrees (WGS84) or meters (Web Mercator)
    lon_minmax: list[float]
    # Spatial reference system: WGS84 (4326, default) or Web Mercator (3857)
    wkid: Literal[3857, 4326] = 4326
    # Output format, more might be supported in the future
    output: Literal["texture"]
    # Additional processing to apply to the elevation data
    processing: Literal[
        "none",
        "hillshade",
        "multi_directional_hillshade",
        "elevation_tinted_hillshade",
        "ellipsoidal_height",
        "slope_degrees_map",
        "aspect_map",
    ] = "none"
    # Size of the output image. If not provided, the default size from adapter config will be used.
    image_size: Optional[list[int]] = None
    # If True and output is TEXTURE, the response will directly contain the image data in base64_image_data
    return_image_data: bool = False
    # If True and output is TEXTURE, the response will directly contain the metadata in metadata
    return_meta_data: bool = False
    # Format of the texture to return (if output is 'texture')
    texture_format: Optional[Literal["png", "jpeg"]] = "png"

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
import io
from PIL import Image
import base64
import numpy as np

# Third party imports
import pytest
from unittest.mock import patch, MagicMock
import xarray as xr

# DFM API imports
from dfm.api import FunctionCall
from dfm.api.dfm import TextureFile
from dfm.api.esri import LoadElevationData as LoadElevationDataParams

# DFM config imports
from dfm.config import SiteConfig
from dfm.config.adapter.esri import LoadElevationData as LoadElevationDataConfig
from dfm.config.provider import EsriProvider as EsriProviderConfig

# DFM service imports
from dfm.service.execute import Site
from dfm.service.execute.provider import EsriProvider
from dfm.service.execute.adapter.esri import LoadElevationData
from dfm.service.execute.adapter.esri._load_elevation_data import (
    PROCESSING_TO_RASTER_FUNCTION,
)

# Test utilities
from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)

# Web Mercator coordinates and distances
WEB_MERCATOR_BASE_X = -11131949.079327168  # Base longitude in Web Mercator
WEB_MERCATOR_BASE_Y = 2273030.926987689  # Base latitude in Web Mercator
WEB_MERCATOR_10_DEGREES = (
    1113194.9079327168  # ~10 degrees distance at equator in Web Mercator
)
WEB_MERCATOR_20_DEGREES = 2 * WEB_MERCATOR_10_DEGREES  # ~20 degrees distance at equator
WEB_MERCATOR_WKID = 3857


@pytest.fixture
def site_config():
    return SiteConfig(
        site="localhost", providers={"esri": EsriProviderConfig(cache_fsspec_conf=None)}
    )


@pytest.fixture
def esri_provider(site_config):
    site = Site(site_config=site_config, site_secrets=None)
    provider = EsriProvider(
        provider="esri", site=site, config=site_config.providers["esri"], secrets=None
    )
    return provider


@pytest.fixture
def mock_elevation_data():
    def _create_mock_data(size=(256, 256), with_transparent_stripes=True):
        """Create a test image with optional transparent stripes.

        Args:
            size (tuple): Size of the image (width, height)
            with_transparent_stripes (bool): Whether to add transparent stripes at top and bottom

        Returns:
            bytes: PNG image data
        """
        width, height = size
        # Create a gradient pattern for more realistic testing
        gradient = np.linspace(0, 255, height, dtype=np.uint8)
        gradient = np.tile(gradient.reshape(-1, 1), (1, width))

        # Create RGBA image with the gradient pattern
        img_array = np.zeros((height, width, 4), dtype=np.uint8)
        img_array[:, :, 0] = gradient  # R channel
        img_array[:, :, 1] = gradient  # G channel
        img_array[:, :, 2] = gradient  # B channel
        img_array[:, :, 3] = 255  # Alpha channel (fully opaque)

        if with_transparent_stripes:
            # Add transparent stripes (20% of height each)
            stripe_height = height // 5

            # Make top and bottom stripes transparent
            img_array[:stripe_height, :, 3] = 0  # Top stripe
            img_array[-stripe_height:, :, 3] = 0  # Bottom stripe

        # Convert to PIL Image
        test_image = Image.fromarray(img_array)

        # Save to bytes
        image_bytes = io.BytesIO()
        test_image.save(image_bytes, format="PNG")
        image_bytes.seek(0)
        return image_bytes.getvalue()

    return _create_mock_data


@pytest.fixture
def mock_esri_service(mock_elevation_data):
    """Mock ESRI service with consistent behavior"""

    class MockEsriService:
        def __init__(self, mock_data_creator):
            self.mock_data_creator = mock_data_creator
            self._imagery_layer_mock = None

        def get_gis(self, *args, **kwargs):
            return MagicMock()

        def get_imagery_layer(self, url, **kwargs):
            # Create a mock that tracks calls
            layer = MagicMock()

            # Configure export_image to return response based on the input size and bbox
            def mock_export_image(**kwargs):
                size = kwargs.get("size", (256, 256))
                bbox = kwargs.get(
                    "bbox",
                    {
                        "xmin": WEB_MERCATOR_BASE_X,
                        "ymin": WEB_MERCATOR_BASE_Y,
                        "xmax": WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES,
                        "ymax": WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES,
                        "spatialReference": {"wkid": WEB_MERCATOR_WKID},
                    },
                )

                # Store the current size for use in download_file
                self.current_size = size

                return {
                    "href": "https://example.com/elevation.png",
                    "width": size[0],
                    "height": size[1],
                    "extent": {
                        "xmin": bbox["xmin"],
                        "ymin": bbox["ymin"],
                        "xmax": bbox["xmax"],
                        "ymax": bbox["ymax"],
                        "spatialReference": {
                            "wkid": WEB_MERCATOR_WKID,
                            "latestWkid": WEB_MERCATOR_WKID,
                        },
                    },
                    "scale": 0,
                }

            layer.export_image = MagicMock(side_effect=mock_export_image)

            # Store the mock so we can inspect calls later
            self._imagery_layer_mock = layer
            return layer

        @property
        def imagery_layer_mock(self):
            return self._imagery_layer_mock

        @property
        def image_data(self):
            # Return image data of the current size
            return self.mock_data_creator(self.current_size)

    return MockEsriService(mock_elevation_data)


def create_adapter(provider, params):
    config = LoadElevationDataConfig(
        image_server="https://example.com/elevation",
        image_size=[256, 256],
        request_retries=3,
        request_timeout=30,
    )
    return LoadElevationData(MockDfmRequest(this_site="here"), provider, config, params)


@pytest.fixture
def execute_adapter_test(esri_provider):
    """Helper fixture to execute adapter tests with common setup pattern."""

    async def _execute(params: LoadElevationDataParams, mock_esri_service):
        with patch(
            "dfm.service.execute.adapter.esri._load_elevation_data.get_gis"
        ) as mock_get_gis, patch(
            "dfm.service.execute.adapter.esri._load_elevation_data.ImageryLayer"
        ) as mock_imagery_layer, patch(
            "dfm.service.execute.adapter.esri._load_elevation_data.apply_raster_function"
        ) as mock_apply_raster:

            mock_get_gis.return_value = mock_esri_service.get_gis()
            mock_imagery_layer.return_value = mock_esri_service.get_imagery_layer(None)

            # Configure apply_raster_function to track calls but still return the layer
            def mock_apply_func(layer, raster_function):
                return layer

            mock_apply_raster.side_effect = mock_apply_func

            adapter = create_adapter(esri_provider, params)

            # Mock the download_file method to return our mock data
            async def mock_download_file(url):
                buffer = io.BytesIO(mock_esri_service.image_data)
                return buffer

            adapter.download_file = mock_download_file

            result = await adapter.body()

            return result, mock_imagery_layer, mock_apply_raster

    return _execute


@pytest.mark.asyncio
async def test_load_elevation_basic(mock_esri_service, execute_adapter_test):
    """Test basic elevation data loading without processing.
    This test serves as a simple example of the adapter's basic functionality."""
    # Arrange
    # Using Web Mercator coordinates for a roughly square region
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, mock_imagery_layer, _ = await execute_adapter_test(
        params, mock_esri_service
    )

    # Assert
    assert isinstance(response, TextureFile)

    # Verify metadata
    assert response.metadata is not None
    # In Web Mercator, equal distances in meters should result in equal pixel dimensions
    assert response.metadata["width"] == 256
    assert response.metadata["height"] == 256
    assert response.metadata["wkid"] == WEB_MERCATOR_WKID
    # Verify full extent in Web Mercator coordinates
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )

    # Verify format and timestamp
    assert response.format == "png"
    assert response.timestamp is not None

    # Verify correct export parameters were used
    export_call = mock_esri_service.imagery_layer_mock.export_image.call_args
    assert export_call is not None
    export_kwargs = export_call[1]
    assert export_kwargs["export_format"] == "png32"
    assert export_kwargs["size"] == (256, 256)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "processing",
    [
        pytest.param("none", id="no_processing"),
        pytest.param("hillshade", id="hillshade"),
        pytest.param("multi_directional_hillshade", id="multi_directional_hillshade"),
        pytest.param("elevation_tinted_hillshade", id="elevation_tinted_hillshade"),
        pytest.param("ellipsoidal_height", id="ellipsoidal_height"),
        pytest.param("slope_degrees_map", id="slope_degrees_map"),
        pytest.param("aspect_map", id="aspect_map"),
    ],
)
async def test_load_elevation_with_processing(
    processing, mock_esri_service, execute_adapter_test
):
    """Test elevation data loading with different processing types"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[20.0, 40.0],
        lon_minmax=[10.0, 30.0],
        wkid=4326,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        processing=processing,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, mock_imagery_layer, mock_apply_raster = await execute_adapter_test(
        params, mock_esri_service
    )

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    assert response.format == "png"

    # Verify processing was applied if specified
    if processing:
        # Verify export_image was called
        assert mock_esri_service.imagery_layer_mock.export_image.called

        # Verify apply_raster_function was called with correct parameters
        assert mock_apply_raster.call_count == 1
        call_args = mock_apply_raster.call_args
        assert call_args is not None
        # apply_raster_function is called with (layer, raster_function_name)
        # where raster_function_name is the ESRI service name from the mapping
        layer_arg, raster_function_name = call_args[0]  # Get both positional arguments
        assert raster_function_name == PROCESSING_TO_RASTER_FUNCTION[processing]
    else:
        # When no processing is specified, apply_raster_function should not be called
        assert mock_apply_raster.call_count == 0


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test xarray output yet")
async def test_load_elevation_as_xarray(mock_esri_service, execute_adapter_test):
    """Test loading elevation data as xarray output"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[20.0, 40.0],
        lon_minmax=[10.0, 30.0],
        wkid=4326,
        output="xarray",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, xr.Dataset)
    assert "terrain" in response.data_vars
    assert (
        response.terrain.attrs["description"] == "Terrain data from raw PNG (grayscale)"
    )
    assert response.terrain.rio.crs == "EPSG:4326"


@pytest.mark.asyncio
async def test_load_elevation_metadata_only(mock_esri_service, execute_adapter_test):
    """Test loading elevation data with metadata only"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[20.0, 40.0],
        lon_minmax=[10.0, 30.0],
        wkid=4326,
        output="texture",
        return_image_data=False,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    assert response.base64_image_data is None
    assert response.format == "png"
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_load_elevation_image_only(mock_esri_service, execute_adapter_test):
    """Test loading elevation data with image only, no metadata"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=False,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is None
    assert response.base64_image_data is not None
    assert response.format == "png"
    assert response.timestamp is not None


@pytest.mark.asyncio
async def test_load_elevation_custom_image_size(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with custom image size"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        image_size=[512, 512],
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    assert response.metadata["width"] == 512
    assert response.metadata["height"] == 512  # Square region should maintain 1:1 ratio

    # Verify export parameters match the custom size
    export_call = mock_esri_service.imagery_layer_mock.export_image.call_args
    assert export_call is not None
    export_kwargs = export_call[1]
    assert export_kwargs["size"] == (512, 512)


@pytest.mark.asyncio
async def test_load_elevation_with_rectangular_region(
    mock_esri_service, execute_adapter_test
):
    """Test elevation data loading with a rectangular region to verify aspect ratio handling"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)

    # Verify metadata
    assert response.metadata is not None
    # For this region, width is twice the height in meters
    # So if width is 256, height should be 128
    assert response.metadata["width"] == 256
    assert response.metadata["height"] == 128
    assert response.metadata["wkid"] == WEB_MERCATOR_WKID
    # Verify full extent in Web Mercator coordinates for 2:1 aspect ratio region
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )

    # Verify export parameters match the adjusted dimensions
    export_call = mock_esri_service.imagery_layer_mock.export_image.call_args
    assert export_call is not None
    export_kwargs = export_call[1]
    assert export_kwargs["size"] == (256, 128)


def test_adjust_image_size_square_region_web_mercator(site_config, esri_provider):
    """Test image size adjustment for a square region in Web Mercator."""
    # Create adapter instance for testing
    FunctionCall.set_allow_outside_block()
    adapter = create_adapter(
        esri_provider,
        LoadElevationDataParams(
            lat_minmax=[0, 1],
            lon_minmax=[0, 1],
            wkid=WEB_MERCATOR_WKID,
            output="texture",
            texture_format="png",
            return_image_data=True,
            return_meta_data=True,
        ),
    )
    FunctionCall.unset_allow_outside_block()
    # Using a square region in Web Mercator (equal distances)
    result = adapter._adjust_image_size(
        WEB_MERCATOR_BASE_X,
        WEB_MERCATOR_BASE_Y,
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES,
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES,
        WEB_MERCATOR_WKID,
        256,
    )

    # For a square region, width and height should be equal
    assert result == (256, 256)


def test_adjust_image_size_rectangular_region_web_mercator(site_config, esri_provider):
    """Test image size adjustment for a rectangular region in Web Mercator."""
    FunctionCall.set_allow_outside_block()
    adapter = create_adapter(
        esri_provider,
        LoadElevationDataParams(
            lat_minmax=[0, 1],
            lon_minmax=[0, 1],
            wkid=WEB_MERCATOR_WKID,
            output="texture",
            texture_format="png",
            return_image_data=True,
            return_meta_data=True,
        ),
    )
    FunctionCall.unset_allow_outside_block()
    result = adapter._adjust_image_size(
        WEB_MERCATOR_BASE_X,
        WEB_MERCATOR_BASE_Y,
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES,
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES,
        WEB_MERCATOR_WKID,
        256,
    )

    assert result == (256, 128)


def test_adjust_image_size_wgs84(site_config, esri_provider):
    """Test image size adjustment for coordinates in WGS84."""
    FunctionCall.set_allow_outside_block()
    adapter = create_adapter(
        esri_provider,
        LoadElevationDataParams(
            lat_minmax=[0, 1],
            lon_minmax=[0, 1],
            wkid=WEB_MERCATOR_WKID,
            output="texture",
            texture_format="png",
            return_image_data=True,
            return_meta_data=True,
        ),
    )
    FunctionCall.unset_allow_outside_block()
    result = adapter._adjust_image_size(-100.0, 30.0, -90.0, 35.0, 4326, 200)

    width, height = result
    assert width == 200
    assert height < width
    assert isinstance(height, int)


def test_adjust_image_size_rounding(site_config, esri_provider):
    """Test rounding behavior of the image size adjustment."""
    FunctionCall.set_allow_outside_block()
    adapter = create_adapter(
        esri_provider,
        LoadElevationDataParams(
            lat_minmax=[0, 1],
            lon_minmax=[0, 1],
            wkid=WEB_MERCATOR_WKID,
            output="texture",
            texture_format="png",
            return_image_data=True,
            return_meta_data=True,
        ),
    )
    FunctionCall.unset_allow_outside_block()
    result = adapter._adjust_image_size(
        WEB_MERCATOR_BASE_X,
        WEB_MERCATOR_BASE_Y,
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES,
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES * 0.7,
        WEB_MERCATOR_WKID,
        100,
    )

    width, height = result
    assert isinstance(width, int)
    assert isinstance(height, int)
    assert height == 70
    assert width == 100


def test_adjust_image_size_different_desired_widths(site_config, esri_provider):
    """Test image size adjustment with different desired widths."""
    FunctionCall.set_allow_outside_block()
    adapter = create_adapter(
        esri_provider,
        LoadElevationDataParams(
            lat_minmax=[0, 1],
            lon_minmax=[0, 1],
            wkid=WEB_MERCATOR_WKID,
            output="texture",
            texture_format="png",
            return_image_data=True,
            return_meta_data=True,
        ),
    )
    FunctionCall.unset_allow_outside_block()
    region = (
        WEB_MERCATOR_BASE_X,
        WEB_MERCATOR_BASE_Y,
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES,
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES,
    )

    result_256 = adapter._adjust_image_size(
        *region, wkid=WEB_MERCATOR_WKID, desired_width=256
    )
    result_512 = adapter._adjust_image_size(
        *region, wkid=WEB_MERCATOR_WKID, desired_width=512
    )

    assert result_256[0] / result_256[1] == pytest.approx(result_512[0] / result_512[1])
    assert result_512[0] == result_256[0] * 2
    assert result_512[1] == result_256[1] * 2


@pytest.mark.asyncio
async def test_load_elevation_jpeg_conversion(mock_esri_service, execute_adapter_test):
    """Test elevation data loading with JPEG conversion."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="jpeg",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.format == "jpeg"
    assert response.base64_image_data is not None

    # Verify the image can be loaded and is in RGB mode
    img_data = base64.b64decode(response.base64_image_data)
    img = Image.open(io.BytesIO(img_data))
    assert img.mode == "RGB"  # JPEG should be in RGB mode


@pytest.mark.asyncio
async def test_load_elevation_coordinate_wrapping(
    mock_esri_service, execute_adapter_test
):
    """Test elevation data loading with coordinate wrapping."""
    test_cases = [
        # Standard case within -180 to 180
        {"lon_min": -170, "lon_max": 170, "expected_min": -170, "expected_max": 170},
        # Case with coordinates > 180
        {"lon_min": 350, "lon_max": 380, "expected_min": 350, "expected_max": 380},
        # Case with coordinates < -180
        {"lon_min": -190, "lon_max": -170, "expected_min": -190, "expected_max": -170},
    ]

    for case in test_cases:
        FunctionCall.set_allow_outside_block()
        params = LoadElevationDataParams(
            lat_minmax=[20.0, 40.0],
            lon_minmax=[case["lon_min"], case["lon_max"]],
            wkid=4326,
            output="texture",
            return_image_data=True,
            return_meta_data=True,
            texture_format="png",
        )
        FunctionCall.unset_allow_outside_block()

        response, _, _ = await execute_adapter_test(params, mock_esri_service)

        assert isinstance(response, TextureFile)
        assert response.metadata is not None
        # Round to 6 decimal places for comparison
        actual_min = response.metadata["lon_minmax"][0]
        actual_max = response.metadata["lon_minmax"][1]
        assert actual_min == pytest.approx(case["expected_min"], abs=1e-6)
        assert actual_max == pytest.approx(case["expected_max"], abs=1e-6)


@pytest.mark.asyncio
async def test_load_elevation_alpha_handling(mock_esri_service, execute_adapter_test):
    """Test elevation data loading with proper alpha channel handling."""
    # Test both PNG and JPEG formats
    for texture_format in ["png", "jpeg"]:
        FunctionCall.set_allow_outside_block()
        params = LoadElevationDataParams(
            lat_minmax=[
                WEB_MERCATOR_BASE_Y,
                WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES,
            ],
            lon_minmax=[
                WEB_MERCATOR_BASE_X,
                WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES,
            ],
            wkid=WEB_MERCATOR_WKID,
            output="texture",
            return_image_data=True,
            return_meta_data=True,
            texture_format=texture_format,
        )
        FunctionCall.unset_allow_outside_block()

        # Act
        response, _, _ = await execute_adapter_test(params, mock_esri_service)

        # Assert
        assert isinstance(response, TextureFile)
        assert response.format == texture_format

        # Verify image format and mode
        img_data = base64.b64decode(response.base64_image_data)
        img = Image.open(io.BytesIO(img_data))
        if texture_format == "jpeg":
            assert img.mode == "RGB"  # JPEG should be RGB
        else:
            assert img.mode in ["RGBA", "RGB"]  # PNG can be either RGBA or RGB


@pytest.mark.asyncio
async def test_transparent_stripe_handling(mock_esri_service, execute_adapter_test):
    """Test that transparent stripes are properly removed from the elevation data."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.base64_image_data is not None

    # Decode and load the image
    image_data = base64.b64decode(response.base64_image_data)
    img = Image.open(io.BytesIO(image_data))

    # Convert to numpy array for analysis
    img_array = np.array(img)

    # Check that the image is in RGBA mode
    assert img.mode == "RGBA"

    # Original image had 20% transparent stripes at top and bottom
    # After processing, these should be removed, resulting in a smaller image
    original_height = 256
    stripe_height = original_height // 5
    expected_height = original_height - (
        2 * stripe_height
    )  # Remove top and bottom stripes

    # Verify the image dimensions are reduced by removing the stripes
    assert img.size == (256, expected_height)

    # Get alpha channel
    alpha = img_array[:, :, 3]

    # Check that there are no transparent pixels in the output
    assert np.all(alpha == 255), "Output image should have no transparent pixels"


@pytest.mark.asyncio
async def test_transparent_stripe_handling_jpeg(
    mock_esri_service, execute_adapter_test
):
    """Test that transparent stripes are properly removed when converting to JPEG."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="jpeg",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.base64_image_data is not None

    # Decode and load the image
    image_data = base64.b64decode(response.base64_image_data)
    img = Image.open(io.BytesIO(image_data))

    # Check that the image is in RGB mode (JPEG doesn't support alpha)
    assert img.mode == "RGB"

    # Original image had 20% transparent stripes at top and bottom
    # After processing, these should be removed, resulting in a smaller image
    original_height = 256
    stripe_height = original_height // 5
    expected_height = original_height - (
        2 * stripe_height
    )  # Remove top and bottom stripes

    # Verify the image dimensions are reduced by removing the stripes
    assert img.size == (256, expected_height)

    # Convert to numpy array for analysis
    img_array = np.array(img)

    # Verify that the image content is preserved (no white fill)
    assert not np.all(img_array[0] == [255, 255, 255]), "Top row should not be white"
    assert not np.all(
        img_array[-1] == [255, 255, 255]
    ), "Bottom row should not be white"


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test invalid coordinates yet")
async def test_invalid_coordinates(mock_esri_service, execute_adapter_test):
    """Test loading elevation data with invalid coordinates."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[91.0, 92.0],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    with pytest.raises(ValueError):
        await execute_adapter_test(params, mock_esri_service)


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test invalid image size yet")
async def test_invalid_image_size(mock_esri_service, execute_adapter_test):
    """Test loading elevation data with invalid image size."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        image_size=[-1, 256],
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    with pytest.raises(ValueError):
        await execute_adapter_test(params, mock_esri_service)


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test unsupported texture format yet")
async def test_unsupported_texture_format(mock_esri_service, execute_adapter_test):
    """Test loading elevation data with unsupported texture format."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="bmp",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    with pytest.raises(ValueError):
        await execute_adapter_test(params, mock_esri_service)


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test coordinates exactly at 180°/-180° yet")
async def test_load_elevation_with_coordinates_exactly_at_180(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with coordinates exactly at 180°/-180°."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    # Verify full extent in Web Mercator coordinates
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test very small regions yet")
async def test_load_elevation_with_very_small_region(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with very small regions (near zero width/height)."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    # Verify full extent in Web Mercator coordinates
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test very large regions yet")
async def test_load_elevation_with_very_large_region(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with very large regions."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    # Verify full extent in Web Mercator coordinates
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test completely transparent image yet")
async def test_load_elevation_with_completely_transparent_image(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with completely transparent image."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    assert response.base64_image_data is None
    assert response.format == "png"
    assert response.timestamp is not None


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test non-standard aspect ratio yet")
async def test_load_elevation_with_non_standard_aspect_ratio(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with non-standard aspect ratio."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES],
        wkid=WEB_MERCATOR_WKID,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    # Verify full extent in Web Mercator coordinates for 2:1 aspect ratio region
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_20_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )


@pytest.mark.asyncio
@pytest.mark.skip(reason="We don't test different WKID projection yet")
async def test_load_elevation_with_different_wkid(
    mock_esri_service, execute_adapter_test
):
    """Test loading elevation data with different WKID projection."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadElevationDataParams(
        lat_minmax=[WEB_MERCATOR_BASE_Y, WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES],
        lon_minmax=[WEB_MERCATOR_BASE_X, WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES],
        wkid=4326,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, TextureFile)
    assert response.metadata is not None
    # Verify full extent in Web Mercator coordinates
    assert response.metadata["lon_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_X)
    assert response.metadata["lon_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_X + WEB_MERCATOR_10_DEGREES
    )
    assert response.metadata["lat_minmax"][0] == pytest.approx(WEB_MERCATOR_BASE_Y)
    assert response.metadata["lat_minmax"][1] == pytest.approx(
        WEB_MERCATOR_BASE_Y + WEB_MERCATOR_10_DEGREES
    )

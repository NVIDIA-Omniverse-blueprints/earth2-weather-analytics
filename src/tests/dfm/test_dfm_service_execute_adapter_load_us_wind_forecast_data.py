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
import json
from datetime import datetime, timezone

# Third party imports
import pytest
from unittest.mock import patch, MagicMock

# DFM API imports
from dfm.api import FunctionCall
from dfm.api.dfm import GeoJsonFile
from dfm.api.esri import LoadUSWindForecastData as LoadUSWindForecastDataParams

# DFM config imports
from dfm.config import SiteConfig
from dfm.config.adapter.esri import (
    LoadUSWindForecastData as LoadUSWindForecastDataConfig,
)
from dfm.config.provider import EsriProvider as EsriProviderConfig

# DFM service imports
from dfm.service.execute import Site
from dfm.service.execute.provider import EsriProvider
from dfm.service.execute.adapter.esri._load_us_wind_forecast_data import (
    LoadUSWindForecastData,
    LAYER_VALUES,
)

# Test utilities
from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


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
def mock_wind_data():
    with open("tests/files/example_esri_us_wind_forecast.json") as f:
        return json.load(f)


@pytest.fixture
def mock_esri_service(mock_wind_data):
    """Mock ESRI service with consistent behavior"""

    class MockEsriService:
        def __init__(self, geojson_data, timestamp):
            self.geojson_data = geojson_data
            self.timestamp = timestamp
            self._feature_layer_mock = None

        def get_gis(self, *args, **kwargs):
            return MagicMock()

        def get_feature_layer(self, url, **kwargs):
            # Create a mock that tracks calls
            feature = MagicMock()

            # Configure query response
            qr = MagicMock()
            qr.to_json = json.dumps(self.geojson_data)
            query_mock = MagicMock(return_value=qr)
            feature.query = query_mock

            # Configure timestamp
            feature.properties = MagicMock()
            feature.properties.timeInfo = MagicMock()
            feature.properties.timeInfo.timeExtent = MagicMock()
            feature.properties.timeInfo.timeExtent.__getitem__ = MagicMock(
                return_value=self.timestamp
            )

            # Store the mock so we can inspect calls later
            self._feature_layer_mock = feature
            return feature

        @property
        def feature_layer_mock(self):
            return self._feature_layer_mock

    timestamp = datetime(2025, 4, 3, 9, 0, tzinfo=timezone.utc).timestamp() * 1000
    return MockEsriService(mock_wind_data, timestamp)


def create_adapter(provider, params):
    config = LoadUSWindForecastDataConfig()
    return LoadUSWindForecastData(
        MockDfmRequest(this_site="here"), provider, config, params
    )


@pytest.fixture
def execute_adapter_test(esri_provider):
    """Helper fixture to execute adapter tests with common setup pattern."""

    async def _execute(params: LoadUSWindForecastDataParams, mock_esri_service):
        with patch(
            "dfm.service.execute.adapter.esri._load_us_wind_forecast_data.get_gis"
        ) as mock_get_gis, patch(
            "dfm.service.execute.adapter.esri._load_us_wind_forecast_data.FeatureLayer"
        ) as mock_feature_layer:

            mock_get_gis.return_value = mock_esri_service.get_gis()
            mock_feature_layer.side_effect = mock_esri_service.get_feature_layer

            adapter = create_adapter(esri_provider, params)
            result = []
            async for r in await adapter.get_or_create_stream():
                result.append(r)

            return result[0] if result else None, mock_feature_layer

    return _execute


@pytest.mark.asyncio
async def test_load_wind_forecast_basic(mock_esri_service, execute_adapter_test):
    """Test basic wind forecast data loading without filters.
    This test serves as a simple example of the adapter's basic functionality."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadUSWindForecastDataParams(
        layer="national", return_geojson=True, return_meta_data=True
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, mock_feature_layer = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify metadata
    assert response.metadata is not None
    expected_timestamp = datetime.fromtimestamp(
        mock_esri_service.timestamp / 1000.0, timezone.utc
    ).strftime("%Y-%m-%dT%H:%M")
    assert response.timestamp == expected_timestamp
    assert "features" in response.metadata

    # Verify data
    assert response.data is not None
    parsed_data = json.loads(response.data)
    assert parsed_data == mock_esri_service.geojson_data

    # Verify correct layer was queried
    feature_layer_call = mock_feature_layer.call_args
    assert feature_layer_call[0][0].endswith(f"/{LAYER_VALUES['national']}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "layer",
    [
        pytest.param("national", id="national"),
        pytest.param("regional", id="regional"),
        pytest.param("state", id="state"),
        pytest.param("county", id="county"),
        pytest.param("district", id="district"),
        pytest.param("block_group", id="block_group"),
        pytest.param("city", id="city"),
    ],
)
async def test_load_wind_forecast_for_layer(
    layer, mock_esri_service, execute_adapter_test
):
    """Test wind forecast data loading for each available layer"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadUSWindForecastDataParams(
        layer=layer, return_geojson=True, return_meta_data=True
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, mock_feature_layer = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify metadata
    assert response.metadata is not None
    expected_timestamp = datetime.fromtimestamp(
        mock_esri_service.timestamp / 1000.0, timezone.utc
    ).strftime("%Y-%m-%dT%H:%M")
    assert response.timestamp == expected_timestamp
    assert "features" in response.metadata

    # Verify data
    assert response.data is not None
    parsed_data = json.loads(response.data)
    assert parsed_data == mock_esri_service.geojson_data

    # Verify correct layer was queried
    feature_layer_call = mock_feature_layer.call_args
    assert feature_layer_call[0][0].endswith(f"/{LAYER_VALUES[layer]}")


@pytest.mark.asyncio
async def test_load_wind_forecast_with_time_filter(
    mock_esri_service, execute_adapter_test
):
    """Test wind forecast data loading with time filter"""
    # Arrange
    time_filter = ["2025-04-03T09:00", "2025-04-03T12:00"]
    FunctionCall.set_allow_outside_block()
    params = LoadUSWindForecastDataParams(
        layer="national",
        time_filter=time_filter,
        return_geojson=True,
        return_meta_data=True,
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)
    assert response.metadata is not None
    assert response.data is not None

    # Verify time filter was applied correctly
    assert mock_esri_service.feature_layer_mock.query.call_args is not None
    query_kwargs = mock_esri_service.feature_layer_mock.query.call_args.kwargs
    assert "time_filter" in query_kwargs
    passed_time_filter = query_kwargs["time_filter"]

    # Verify time filter values are datetime objects with correct values
    assert len(passed_time_filter) == 2
    expected_start = datetime.strptime(
        time_filter[0], LoadUSWindForecastData.DATE_FORMAT
    )
    expected_end = datetime.strptime(time_filter[1], LoadUSWindForecastData.DATE_FORMAT)
    assert passed_time_filter[0] == expected_start
    assert passed_time_filter[1] == expected_end


@pytest.mark.asyncio
async def test_load_wind_forecast_metadata_only(
    mock_esri_service, execute_adapter_test
):
    """Test wind forecast data loading with metadata only"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadUSWindForecastDataParams(
        layer="national", return_geojson=False, return_meta_data=True
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify metadata is present and correct
    assert response.metadata is not None
    assert "features" in response.metadata
    assert response.timestamp is not None

    # Verify no GeoJSON data is returned
    assert response.data is None

    # Verify we still queried the data (needed for metadata)
    assert mock_esri_service.feature_layer_mock.query.called


@pytest.mark.asyncio
async def test_load_wind_forecast_geojson_only(mock_esri_service, execute_adapter_test):
    """Test wind forecast data loading with GeoJSON only, no metadata"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadUSWindForecastDataParams(
        layer="national", return_geojson=True, return_meta_data=False
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify GeoJSON data is present and correct
    assert response.data is not None
    parsed_data = json.loads(response.data)
    assert parsed_data == mock_esri_service.geojson_data

    # Verify timestamp is still present (it's a required field)
    assert response.timestamp is not None

    # Verify no metadata is returned
    assert response.metadata is None

    # Verify we still queried the data
    assert mock_esri_service.feature_layer_mock.query.called

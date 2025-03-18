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

# Third party imports
import pytest
from unittest.mock import patch, MagicMock

# DFM API imports
from dfm.api import FunctionCall
from dfm.api.dfm import GeoJsonFile
from dfm.api.esri import LoadMetarWindData as LoadMetarWindDataParams

# DFM config imports
from dfm.config import SiteConfig
from dfm.config.adapter.esri import LoadMetarWindData as LoadMetarWindDataConfig
from dfm.config.provider import EsriProvider as EsriProviderConfig

# DFM service imports
from dfm.service.execute import Site
from dfm.service.execute.provider import EsriProvider
from dfm.service.execute.adapter.esri._load_metar_wind_data import (
    LoadMetarWindData,
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
def mock_metar_data():
    # Example METAR data structure
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.31, 47.45]},
                "properties": {
                    "station_id": "KSEA",
                    "wind_speed": 10,
                    "wind_direction": 270,
                    "observation_time": "2025-04-03T09:00:00Z",
                },
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.18, 47.68]},
                "properties": {
                    "station_id": "KBFI",
                    "wind_speed": 8,
                    "wind_direction": 290,
                    "observation_time": "2025-04-03T09:00:00Z",
                },
            },
        ],
    }


@pytest.fixture
def mock_esri_service(mock_metar_data):
    """Mock ESRI service with consistent behavior"""

    class MockEsriService:
        def __init__(self, geojson_data):
            self.geojson_data = geojson_data
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

            # Store the mock so we can inspect calls later
            self._feature_layer_mock = feature
            return feature

        @property
        def feature_layer_mock(self):
            return self._feature_layer_mock

    return MockEsriService(mock_metar_data)


def create_adapter(provider, params):
    config = LoadMetarWindDataConfig()
    return LoadMetarWindData(MockDfmRequest(this_site="here"), provider, config, params)


@pytest.fixture
def execute_adapter_test(esri_provider):
    """Helper fixture to execute adapter tests with common setup pattern."""

    async def _execute(params: LoadMetarWindDataParams, mock_esri_service):
        with patch(
            "dfm.service.execute.adapter.esri._load_metar_wind_data.get_gis"
        ) as mock_get_gis, patch(
            "dfm.service.execute.adapter.esri._load_metar_wind_data.FeatureLayer"
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
async def test_load_metar_wind_basic(mock_esri_service, execute_adapter_test):
    """Test basic METAR wind data loading.
    This test serves as a simple example of the adapter's basic functionality."""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadMetarWindDataParams(
        layer="stations", return_geojson=True, return_meta_data=True
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, mock_feature_layer = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify metadata
    assert response.metadata is not None
    assert response.metadata["features"] == str(
        len(mock_esri_service.geojson_data["features"])
    )
    assert response.metadata["layer"] == "stations"

    # Verify data
    assert response.data is not None
    parsed_data = json.loads(response.data)
    assert parsed_data == mock_esri_service.geojson_data

    # Verify correct layer was queried
    feature_layer_call = mock_feature_layer.call_args
    assert feature_layer_call[0][0].endswith(f"/{LAYER_VALUES['stations']}")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "layer",
    [
        pytest.param("stations", id="stations"),
        pytest.param("buoys", id="buoys"),
    ],
)
async def test_load_metar_wind_for_layer(
    layer, mock_esri_service, execute_adapter_test
):
    """Test METAR wind data loading for each available layer"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadMetarWindDataParams(
        layer=layer, return_geojson=True, return_meta_data=True
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, mock_feature_layer = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify metadata
    assert response.metadata is not None
    assert response.metadata["features"] == str(
        len(mock_esri_service.geojson_data["features"])
    )
    assert response.metadata["layer"] == layer

    # Verify data
    assert response.data is not None
    parsed_data = json.loads(response.data)
    assert parsed_data == mock_esri_service.geojson_data

    # Verify correct layer was queried
    feature_layer_call = mock_feature_layer.call_args
    assert feature_layer_call[0][0].endswith(f"/{LAYER_VALUES[layer]}")


@pytest.mark.asyncio
async def test_load_metar_wind_metadata_only(mock_esri_service, execute_adapter_test):
    """Test METAR wind data loading with metadata only"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadMetarWindDataParams(
        layer="stations", return_geojson=False, return_meta_data=True
    )
    FunctionCall.unset_allow_outside_block()

    # Act
    response, _ = await execute_adapter_test(params, mock_esri_service)

    # Assert
    assert isinstance(response, GeoJsonFile)

    # Verify metadata is present and correct
    assert response.metadata is not None
    assert response.metadata["features"] == str(
        len(mock_esri_service.geojson_data["features"])
    )
    assert response.metadata["layer"] == "stations"
    assert response.timestamp is not None

    # Verify no GeoJSON data is returned
    assert response.data is None

    # Verify we still queried the data (needed for metadata)
    assert mock_esri_service.feature_layer_mock.query.called


@pytest.mark.asyncio
async def test_load_metar_wind_geojson_only(mock_esri_service, execute_adapter_test):
    """Test METAR wind data loading with GeoJSON only, no metadata"""
    # Arrange
    FunctionCall.set_allow_outside_block()
    params = LoadMetarWindDataParams(
        layer="stations", return_geojson=True, return_meta_data=False
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

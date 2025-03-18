# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import json
import base64
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from dfm.api import FunctionCall
from dfm.api.dfm import TextureFile
from dfm.api.esri import LoadElevationData
from dfm.service.execute.adapter.esri._load_elevation_data import (
    ElevationMapImageCachingIterator,
)

pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.base_url = "/cache"
    config.protocol = "file"  # Using 'file' protocol for local filesystem
    config.cache_folder = "/cache/path"  # Set the cache folder path in config
    return config


@pytest.fixture
def mock_adapter():
    adapter = MagicMock()
    FunctionCall.set_allow_outside_block()
    adapter.params = LoadElevationData(
        lat_minmax=[20.0, 40.0],
        lon_minmax=[10.0, 30.0],
        wkid=4326,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()
    return adapter


@pytest.fixture
def mock_filesystem():
    fs = MagicMock()
    fs.pipe = MagicMock()
    fs.exists = MagicMock()
    fs.open = MagicMock()
    return fs


@pytest_asyncio.fixture
async def caching_iterator(mock_adapter, mock_filesystem, mock_config):
    with patch("fsspec.filesystem", return_value=mock_filesystem):
        iterator = ElevationMapImageCachingIterator(mock_adapter, mock_config)
        return iterator


@pytest.mark.asyncio
async def test_cache_file_name_basic(caching_iterator):
    """Test basic cache file name generation without processing."""
    expected = "10-00_20-00_30-00_40-00_4326_none_4326.png"
    assert caching_iterator.get_cache_file_name() == expected


@pytest.mark.asyncio
async def test_cache_file_name_for_each_processing(
    mock_adapter, mock_filesystem, mock_config
):
    """Test file name generation for each Processing enum value."""
    expected_names = {
        "none": "10-00_20-00_30-00_40-00_4326_none_4326.png",
        "hillshade": "10-00_20-00_30-00_40-00_4326_hillshade_4326.png",
        "multi_directional_hillshade": "10-00_20-00_30-00_40-00_4326_multi_directional_hillshade_4326.png",
        "elevation_tinted_hillshade": "10-00_20-00_30-00_40-00_4326_elevation_tinted_hillshade_4326.png",
        "ellipsoidal_height": "10-00_20-00_30-00_40-00_4326_ellipsoidal_height_4326.png",
        "slope_degrees_map": "10-00_20-00_30-00_40-00_4326_slope_degrees_map_4326.png",
        "aspect_map": "10-00_20-00_30-00_40-00_4326_aspect_map_4326.png",
    }

    for processing, expected_name in expected_names.items():
        # Configure adapter for this processing type
        FunctionCall.set_allow_outside_block()
        mock_adapter.params = LoadElevationData(
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

        with patch("fsspec.filesystem", return_value=mock_filesystem):
            iterator = ElevationMapImageCachingIterator(mock_adapter, mock_config)
            assert (
                iterator.get_cache_file_name() == expected_name
            ), f"Failed for processing {processing}"


@pytest.mark.asyncio
async def test_write_value_to_cache(caching_iterator):
    """Test write_value_to_cache method - should be a no-op."""
    # This method is documented to do nothing, as the adapter handles writes
    await caching_iterator.write_value_to_cache(1, {"test": "data"})
    # No assertions needed as method is explicitly a no-op


@pytest.mark.asyncio
async def test_write_file_bytes_content(caching_iterator):
    """Test writing bytes content to a file."""
    content = b"test image data"
    filename = "test.png"

    result = caching_iterator.write_file(filename, content)

    caching_iterator.filesystem.pipe.assert_called_once()
    args = caching_iterator.filesystem.pipe.call_args[0]
    assert args[1] == content
    assert result.startswith("/cache")
    assert result.endswith("/test.png")


@pytest.mark.asyncio
async def test_write_file_json_content(caching_iterator):
    """Test writing JSON content to a file."""
    content = {"test": "data"}
    filename = "metadata.json"

    result = caching_iterator.write_file(filename, content)

    caching_iterator.filesystem.pipe.assert_called_once()
    args = caching_iterator.filesystem.pipe.call_args[0]
    assert args[1] == json.dumps(content, indent=4).encode("utf-8")
    assert result.startswith("/cache")
    assert result.endswith("/metadata.json")


@pytest.mark.asyncio
async def test_load_values_from_cache_no_files(caching_iterator, mock_config):
    """Test loading values when neither metadata nor image files exist."""
    # Mock file existence checks - neither metadata nor image exist
    caching_iterator.filesystem.exists.side_effect = [False, False]

    # Create an empty result file to return
    result_file = caching_iterator.get_cache_file_name()
    result_url = f"{caching_iterator.full_cache_folder_path}/{result_file}"

    result = await caching_iterator.load_values_from_cache(1)

    assert len(result) == 1
    assert isinstance(result[0], TextureFile)
    assert result[0].metadata is None
    assert result[0].base64_image_data is None
    assert result[0].metadata_url is None
    assert result[0].url == result_url
    assert result[0].format == "png"
    assert result[0].timestamp == ""  # No metadata, so timestamp is empty string


@pytest.mark.asyncio
async def test_load_values_from_cache_metadata_only(caching_iterator):
    """Test loading values when only metadata exists and is requested."""
    metadata = {
        "timestamp": "2025-04-01T00:00",
        "width": 256,
        "height": 256,
        "lon_minmax": [10.0, 30.0],
        "lat_minmax": [20.0, 40.0],
        "wkid": 4326,
    }

    # Mock file existence checks
    caching_iterator.filesystem.exists.side_effect = [True, False]

    # Mock metadata file read
    mock_metadata_file = MagicMock()
    mock_metadata_file.__enter__.return_value.read.return_value = json.dumps(
        metadata
    ).encode("utf-8")
    caching_iterator.filesystem.open.return_value = mock_metadata_file

    result = await caching_iterator.load_values_from_cache(1)

    assert len(result) == 1
    assert isinstance(result[0], TextureFile)
    assert result[0].metadata == metadata
    assert result[0].base64_image_data is None
    assert result[0].format == "png"
    assert result[0].timestamp == metadata["timestamp"]


@pytest.mark.asyncio
async def test_load_values_from_cache_image_only(caching_iterator, mock_config):
    """Test loading values when only image exists and is requested."""
    # Configure adapter to only request image
    FunctionCall.set_allow_outside_block()
    caching_iterator.adapter.params = LoadElevationData(
        lat_minmax=[20.0, 40.0],
        lon_minmax=[10.0, 30.0],
        wkid=4326,
        output="texture",
        return_image_data=True,
        return_meta_data=False,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Mock file existence checks - metadata doesn't exist, but image does
    caching_iterator.filesystem.exists.side_effect = [False, True]

    # Mock image file read
    image_data = b"test image data"
    mock_image_file = MagicMock()
    mock_image_file.__enter__.return_value.read.return_value = image_data
    caching_iterator.filesystem.open.return_value = mock_image_file

    # Create result file path
    result_file = caching_iterator.get_cache_file_name()
    result_url = f"{caching_iterator.full_cache_folder_path}/{result_file}"

    result = await caching_iterator.load_values_from_cache(1)

    assert len(result) == 1
    assert isinstance(result[0], TextureFile)
    assert result[0].metadata is None
    assert result[0].base64_image_data == base64.b64encode(image_data).decode()
    assert result[0].url == result_url
    assert result[0].metadata_url is None
    assert result[0].format == "png"
    assert result[0].timestamp == ""  # No metadata, so timestamp is empty string


@pytest.mark.asyncio
async def test_load_values_from_cache_both_files_present(caching_iterator, mock_config):
    """Test loading values when both metadata and image exist and are requested."""
    metadata = {
        "timestamp": "2025-04-01T00:00",
        "width": 256,
        "height": 256,
        "lon_minmax": [10.0, 30.0],
        "lat_minmax": [20.0, 40.0],
        "wkid": 4326,
    }
    image_data = b"test image data"

    # Configure adapter to request both
    FunctionCall.set_allow_outside_block()
    caching_iterator.adapter.params = LoadElevationData(
        lat_minmax=[20.0, 40.0],
        lon_minmax=[10.0, 30.0],
        wkid=4326,
        output="texture",
        return_image_data=True,
        return_meta_data=True,
        texture_format="png",
    )
    FunctionCall.unset_allow_outside_block()

    # Mock file existence checks - both files exist
    caching_iterator.filesystem.exists.side_effect = [True, True]

    # Mock file reads
    mock_metadata_file = MagicMock()
    mock_metadata_file.__enter__.return_value.read.return_value = json.dumps(
        metadata
    ).encode("utf-8")

    mock_image_file = MagicMock()
    mock_image_file.__enter__.return_value.read.return_value = image_data

    caching_iterator.filesystem.open.side_effect = [mock_metadata_file, mock_image_file]

    # Create result file paths
    result_file = caching_iterator.get_cache_file_name()
    result_url = f"{caching_iterator.full_cache_folder_path}/{result_file}"
    metadata_url = f"{caching_iterator.full_cache_folder_path}/metadata.json"

    result = await caching_iterator.load_values_from_cache(1)

    assert len(result) == 1
    assert isinstance(result[0], TextureFile)
    assert result[0].metadata == metadata
    assert result[0].base64_image_data == base64.b64encode(image_data).decode()
    assert result[0].url == result_url
    assert result[0].metadata_url == metadata_url
    assert result[0].format == "png"
    assert result[0].timestamp == metadata["timestamp"]

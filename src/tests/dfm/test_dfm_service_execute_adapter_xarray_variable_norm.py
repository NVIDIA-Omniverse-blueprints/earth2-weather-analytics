# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from dfm.api._function_call import FunctionCall
import numpy as np
import pytest
from tests.common._mock_adapter import MockAdapter
from tests.common._mock_dfm_request import MockDfmRequest
import xarray
from datetime import datetime, timedelta

from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import Provider
from dfm.api.xarray import VariableNorm as VariableNormParams
from dfm.service.execute.adapter.xarray import VariableNorm


@pytest.fixture
def mock_request():
    return MockDfmRequest(this_site="test")


@pytest.fixture
def mock_provider():
    return Provider(provider="test")


@pytest.fixture
def mock_adapter():
    # Create a sample dataset with known values
    times = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(2)]
    lats = np.linspace(-90, 90, 6)
    lons = np.linspace(-180, 180, 4)

    # Create two variables with known values
    var1 = np.ones((2, 4, 6)) * 3.0  # All 3's
    var2 = np.ones((2, 4, 6)) * 4.0  # All 4's

    return MockAdapter(
        [
            xarray.Dataset(
                data_vars={
                    "temperature": (("time", "longitude", "latitude"), var1),
                    "humidity": (("time", "longitude", "latitude"), var2),
                },
                coords={
                    "time": times,
                    "latitude": lats,
                    "longitude": lons,
                },
            )
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "variables,expected_norm",
    [
        (["temperature"], 3.0),
        (["temperature", "humidity"], 5.0),
    ],
)
async def test_basic_norm_calculation(
    mock_request, mock_adapter, variables, expected_norm
):
    """Test basic p-norm calculation with default parameters"""
    FunctionCall.set_allow_outside_block()
    params = VariableNormParams(
        data=mock_adapter.node_id, variables=variables  # Not needed for unit test
    )

    adapter = VariableNorm(mock_request, None, None, params, mock_adapter)
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert "norm" in result[0].data_vars
    np.testing.assert_allclose(result[0]["norm"].values, expected_norm)
    assert result[0]["norm"].attrs["p_value"] == 2.0
    assert result[0]["norm"].attrs["data_min"] == expected_norm
    assert result[0]["norm"].attrs["data_max"] == expected_norm


@pytest.mark.asyncio
async def test_custom_p_value(mock_request, mock_adapter):
    """Test p-norm calculation with custom p value"""
    FunctionCall.set_allow_outside_block()
    params = VariableNormParams(
        data=mock_adapter.node_id,
        variables=["temperature", "humidity"],
        p=1.0,  # L1 norm
    )

    adapter = VariableNorm(mock_request, None, None, params, mock_adapter)
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    # For p=1, norm of [3,4] should be |3| + |4| = 7
    expected_norm = 7.0

    assert len(result) == 1
    np.testing.assert_allclose(result[0]["norm"].values, expected_norm)
    assert result[0]["norm"].attrs["p_value"] == 1.0


@pytest.mark.asyncio
async def test_custom_output_name(mock_request, mock_adapter):
    """Test using custom output variable name"""
    FunctionCall.set_allow_outside_block()
    params = VariableNormParams(
        data=mock_adapter.node_id,
        variables=["temperature", "humidity"],
        output_name="combined_norm",
    )

    adapter = VariableNorm(mock_request, None, None, params, mock_adapter)
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert "combined_norm" in result[0].data_vars
    assert "norm" not in result[0].data_vars


@pytest.mark.asyncio
async def test_missing_variable(mock_request, mock_adapter):
    """Test error handling when requesting non-existent variable"""
    FunctionCall.set_allow_outside_block()
    params = VariableNormParams(
        data=mock_adapter.node_id, variables=["temperature", "nonexistent_var"]
    )

    adapter = VariableNorm(mock_request, None, None, params, mock_adapter)
    FunctionCall.unset_allow_outside_block()
    with pytest.raises(
        DataError, match="Variables \\['nonexistent_var'\\] not found in dataset"
    ):
        async for _ in await adapter.get_or_create_stream():
            pass


@pytest.mark.asyncio
async def test_custom_dimensions(mock_request):
    """Test using custom dimension names"""
    # Create dataset with different dimension names
    times = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(2)]
    x = np.linspace(-90, 90, 4)
    y = np.linspace(-180, 180, 6)

    ds = xarray.Dataset(
        data_vars={
            "var1": (("t", "x", "y"), np.ones((2, 4, 6)) * 3.0),
            "var2": (("t", "x", "y"), np.ones((2, 4, 6)) * 4.0),
        },
        coords={
            "t": times,
            "y": y,
            "x": x,
            "phoo": x,
        },
    )

    mock_adapter = MockAdapter([ds])
    FunctionCall.set_allow_outside_block()
    params = VariableNormParams(
        data=mock_adapter.node_id,
        variables=["var1", "var2"],
    )

    adapter = VariableNorm(mock_request, None, None, params, mock_adapter)
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert "norm" in result[0].data_vars
    assert set(result[0].dims) == {"t", "x", "y"}

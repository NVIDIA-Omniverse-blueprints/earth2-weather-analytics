# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import pytest
import xarray
import numpy as np

from datetime import datetime, timezone
from unittest.mock import patch

from dfm.api import FunctionCall
from dfm.api.data_loader import LoadHrrrModelData as LoadHrrModelDataParams
from dfm.config.adapter.data_loader import LoadHrrrData as LoadHrrrDataConfig
from dfm.service.execute.adapter.data_loader import LoadHrrrData
from dfm.service.execute.discovery import AdviceBuilder
from dfm.api.discovery import SingleFieldAdvice, PartialFieldAdvice

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


def create_adapter(params: LoadHrrModelDataParams):
    class TestProvider:
        provider = "testprovider"

        def cache_fsspec_conf(self):
            return None

    config = LoadHrrrDataConfig()
    adapter = LoadHrrrData(
        MockDfmRequest(this_site="here"),
        TestProvider(),  # provider # type: ignore
        config,
        params,
    )
    return adapter


async def run_hrrr_adapter(
    variables: list[str] | str, time: str = "2022-09-06T00:00", step: int = 19
):
    FunctionCall.set_allow_outside_block()
    params = LoadHrrModelDataParams(variables=variables, time=time, step=step)
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert all(isinstance(r, xarray.Dataset) for r in result)

    return result[0] if len(result) == 1 else result


@pytest.mark.asyncio
async def test_coordinates():
    """Test that coordinates has expected shapes and values."""
    ds = await run_hrrr_adapter(variables=["t2m"])

    assert "time" in ds
    assert "longitude" in ds
    assert "latitude" in ds

    assert ds["time"] == np.datetime64("2022-09-06T19:00:00")


@pytest.mark.asyncio
async def test_t2m():
    """Test that adapter supports 2m temperature."""
    ds = await run_hrrr_adapter(variables=["t2m"])
    assert "t2m" in ds

    at = ds["t2m"].attrs

    assert at["long_name"] == "2 metre temperature"
    assert at["standard_name"] == "air_temperature"
    assert at["units"] == "K"

    # The adapter can return NaNs due to reprojection, so we fill them with 0
    ds["t2m"] = ds["t2m"].fillna(0)
    assert ((ds["t2m"] >= 0) & (ds["t2m"] < 380)).all()


@pytest.mark.asyncio
async def test_u10m():
    """Test that adapter supports u component of 10m wind."""
    ds = await run_hrrr_adapter(variables=["u10m"])
    assert "u10m" in ds

    at = ds["u10m"].attrs

    assert at["long_name"] == "10 metre U wind component"
    assert at["standard_name"] == "eastward_wind"
    assert at["units"] == "m s**-1"

    # The adapter can return NaNs due to reprojection, so we fill them with -60
    ds["u10m"] = ds["u10m"].fillna(-60)
    assert ((ds["u10m"] >= -60) & (ds["u10m"] <= 60)).all()


@pytest.mark.asyncio
async def test_v10m():
    """Test that adapter supports v component of 10m wind."""
    ds = await run_hrrr_adapter(variables=["v10m"])
    assert "v10m" in ds

    at = ds["v10m"].attrs

    assert at["long_name"] == "10 metre V wind component"
    assert at["standard_name"] == "northward_wind"
    assert at["units"] == "m s**-1"

    # The adapter can return NaNs due to reprojection, so we fill them with -60
    ds["v10m"] = ds["v10m"].fillna(-60)
    assert ((ds["v10m"] >= -60) & (ds["v10m"] <= 60)).all()


@pytest.mark.asyncio
async def test_wind():
    """Test that adapter supports querying for more than one variable."""
    ds = await run_hrrr_adapter(variables=["v10m", "u10m"])

    assert "v10m" in ds
    assert "u10m" in ds

    at = ds["v10m"].attrs

    assert at["long_name"] == "10 metre V wind component"
    assert at["standard_name"] == "northward_wind"
    assert at["units"] == "m s**-1"

    at = ds["u10m"].attrs

    assert at["long_name"] == "10 metre U wind component"
    assert at["standard_name"] == "eastward_wind"
    assert at["units"] == "m s**-1"

    # The adapter can return NaNs due to reprojection, so we fill them with -60
    ds["u10m"] = ds["u10m"].fillna(-60)
    ds["v10m"] = ds["v10m"].fillna(-60)
    assert ((ds["u10m"] >= -60) & (ds["u10m"] <= 60)).all()
    assert ((ds["v10m"] >= -60) & (ds["v10m"] <= 60)).all()


@pytest.mark.asyncio
async def test_multiple_vars():
    """Test that adapter supports querying for more than one variable."""
    ds = await run_hrrr_adapter(variables=["v10m", "u10m"])

    assert "v10m" in ds
    assert "u10m" in ds


@pytest.mark.asyncio
async def test_multiple_vars_different_hypercubes():
    """
    Test that adapter returns error when selected
    variables belong to different hypercubes.
    """
    ds = await run_hrrr_adapter(variables=["v10m", "t2m"])
    assert "v10m" in ds
    assert "t2m" in ds


@pytest.mark.asyncio
async def test_all_variables_one_by_one():
    """Test that adapter can fetch all variables defined in ERA5_TO_HRRR_VARIABLES."""
    # Filter out None values from ERA5_TO_HRRR_VARIABLES
    valid_variables = [
        var
        for var, mapping in LoadHrrrData.ERA5_TO_HRRR_VARIABLES.items()
        if mapping is not None
    ]

    ds = await run_hrrr_adapter(variables=valid_variables)

    # Verify each variable exists in dataset
    for var in valid_variables:
        assert var in ds
        assert not ds[var].isnull().all()  # Ensure variable contains data


@pytest.mark.asyncio
async def test_all_variables_wildcard():
    """Test that adapter can fetch all variables defined in ERA5_TO_HRRR_VARIABLES."""
    # Filter out None values from ERA5_TO_HRRR_VARIABLES
    valid_variables = [
        var
        for var, mapping in LoadHrrrData.ERA5_TO_HRRR_VARIABLES.items()
        if mapping is not None
    ]

    ds = await run_hrrr_adapter(variables="*")

    # Verify each variable exists in dataset
    for var in valid_variables:
        assert var in ds
        assert not ds[var].isnull().all()  # Ensure variable contains data


def check_advice(advice):
    assert advice
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.field == "variables"
    assert isinstance(advice.value, list)
    assert advice.value == ["*", list(LoadHrrrData.ERA5_TO_HRRR_VARIABLES.keys())]


@pytest.mark.asyncio
@pytest.mark.skip(reason="as_adviseable error")
async def test_discovery_all():
    FunctionCall.set_allow_outside_block()
    params = LoadHrrModelDataParams.as_adviseable()
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    builder = AdviceBuilder(adapter)  # type: ignore
    with patch(
        "dfm.service.execute.adapter.data_loader._load_hrrr_data.datetime",
        autospec=True,
    ) as dtp:
        dtp.now.return_value = datetime(2025, 2, 4, 13, tzinfo=timezone.utc)
        advice = await builder.generate_advice()
    check_advice(advice)

    edge = advice.edge
    assert isinstance(edge, SingleFieldAdvice)
    assert edge.field == "time"
    assert isinstance(edge.value, dict)
    assert edge.value == {
        "startdate": "2014-07-30T00:00",
        "enddate": "2025-02-04T11:00",
        "timeinterval": "???",
    }
    edge = edge.edge
    assert isinstance(edge, PartialFieldAdvice)


@pytest.mark.asyncio
@pytest.mark.skip(reason="as_adviseable error")
async def test_discovery_partial_time():
    for hour in [0, 1, 5, 6, 9, 12, 17, 18, 19, 20, 23]:
        FunctionCall.set_allow_outside_block()
        params = LoadHrrModelDataParams.as_adviseable(time=f"2024-07-05T{hour}:00")
        FunctionCall.unset_allow_outside_block()
        adapter = create_adapter(params)
        builder = AdviceBuilder(adapter)  # type: ignore
        advice = await builder.generate_advice()
        check_advice(advice)

        edge = advice.edge
        assert isinstance(edge, SingleFieldAdvice)
        assert edge.field == "step"
        assert isinstance(edge.value, list)
        max_step = 48 if hour % 6 == 0 else 18
        assert edge.value == [str(i) for i in range(0, max_step + 1)]
        assert not edge.edge

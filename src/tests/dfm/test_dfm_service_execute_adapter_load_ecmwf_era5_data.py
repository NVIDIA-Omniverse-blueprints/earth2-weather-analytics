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
import os
from dfm.api import FunctionCall
from dfm.api.data_loader import LoadEra5ModelData as LoadEra5ModelDataParams
from dfm.config.adapter.data_loader import LoadEcmwfEra5Data as LoadEcmwfEra5DataConfig
from dfm.service.execute.adapter.data_loader import (
    LoadEcmwfEra5Data as LoadEcmwfEra5DataAdapter,
)
from dfm.service.execute.discovery import AdviceBuilder

from tests.common import MockDfmRequest
from tests.dfm.utils import generate_ecmwf_era5_data

pytest_plugins = ("pytest_asyncio",)

TEST_DATA_FILE = "tests/files/adapters_test_ecmwf_era5_data.nc"


def create_adapter(params):
    class TestProvider:
        provider = "testprovider"

        def cache_fsspec_conf(self):
            return None

    config = LoadEcmwfEra5DataConfig(
        chunks="auto",
        url=TEST_DATA_FILE,
        engine=None,
        engine_kwargs=None,
        first_date="1959-01-01",
        last_date="2021-12-31",
        frequency=1,
    )
    adapter = LoadEcmwfEra5DataAdapter(
        MockDfmRequest(this_site="here"),
        TestProvider(),  # provider # type: ignore
        config,
        params,
    )
    return adapter


def prepare_testdata_file():
    """Creates the test netcdf file used in the tests, if it doesn't exist yet"""
    if not os.path.exists(TEST_DATA_FILE):
        ds = generate_ecmwf_era5_data()
        ds.to_netcdf(TEST_DATA_FILE)


@pytest.mark.asyncio
async def test_adapter_executes():
    prepare_testdata_file()

    FunctionCall.set_allow_outside_block()
    params = LoadEra5ModelDataParams(
        variables=["10m_u_component_of_wind"], selection={"time": "2019-09-06T12:00"}
    )
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert isinstance(result[0], xarray.Dataset)
    ds = result[0]
    assert len(ds.variables) == 5  # 4 coordinates and the one variable
    assert "10m_u_component_of_wind" in ds
    assert "time" in ds
    assert "latitude" in ds
    assert "longitude" in ds
    assert "level" in ds


@pytest.mark.asyncio
@pytest.mark.skip(reason="As Adviseable isn't supported, from what I can tell")
async def test_discovery():
    FunctionCall.set_allow_outside_block()
    params = LoadEra5ModelDataParams.as_adviseable()
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)

    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    assert advice

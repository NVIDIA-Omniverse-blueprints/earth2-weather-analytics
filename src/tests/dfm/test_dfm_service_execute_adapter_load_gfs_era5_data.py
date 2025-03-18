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
from dfm.config.adapter.data_loader import LoadGfsEra5Data as LoadGfsEra5DataConfig
from dfm.service.execute.adapter.data_loader import (
    LoadGfsEra5Data as LoadGfsEra5DataAdapter,
)
from dfm.service.execute.discovery import AdviceBuilder

from tests.common import MockDfmRequest
from tests.dfm.utils import generate_gfs_data

pytest_plugins = ("pytest_asyncio",)

TEST_DATA_FILE = "tests/files/adapters_test_gfs_era5_data.nc"


def create_adapter(params: LoadEra5ModelDataParams):
    class TestProvider:
        provider = "testprovider"

        def cache_fsspec_conf(self):
            return None

    config = LoadGfsEra5DataConfig(
        chunks="auto",
        url=TEST_DATA_FILE,
        offset_first=10,
        offset_last=1,
        frequency=3,
    )
    adapter = LoadGfsEra5DataAdapter(
        MockDfmRequest(this_site="here"),
        TestProvider(),  # provider # type: ignore
        config,
        params,
    )
    return adapter


def prepare_testdata_file():
    """Creates the test netcdf file used in the tests, if it doesn't exist yet"""
    if not os.path.exists(TEST_DATA_FILE):
        print(f"Saving gfs test data to {TEST_DATA_FILE}")
        ds = generate_gfs_data()
        ds.to_netcdf(TEST_DATA_FILE)
        ds.close()


@pytest.mark.asyncio
async def test_adapter_executes():
    prepare_testdata_file()
    FunctionCall.set_allow_outside_block()
    params = LoadEra5ModelDataParams(variables="*", selection={"time": "2022-09-06"})
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert isinstance(result[0], xarray.Dataset)
    ds = result[0]

    assert len(ds.variables) == 87 + 3
    assert "u1000" in ds
    assert "time" in ds
    assert "lat" in ds
    assert "lon" in ds


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

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
from dfm.api import FunctionCall
from dfm.api.data_loader import LoadEra5ModelData as LoadEra5ModelDataParams
from dfm.config.adapter.data_loader import LoadGfsEra5S3Data as LoadGfsEra5S3DataConfig
from dfm.service.execute.adapter.data_loader import (
    LoadGfsEra5S3Data as LoadGfsEra5S3DataAdapter,
)
from dfm.service.execute.discovery import AdviceBuilder

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


def create_adapter(params: LoadEra5ModelDataParams):
    class TestProvider:
        provider = "testprovider"

        def cache_fsspec_conf(self):
            return None

    config = LoadGfsEra5S3DataConfig(
        chunks="auto",
        bucket_name="noaa-gfs-bdp-pds",
        first_date="2021-02-18",
        last_date="2024-03-13",
        frequency=6,
    )
    adapter = LoadGfsEra5S3DataAdapter(
        MockDfmRequest(this_site="here"),
        TestProvider(),  # provider # type: ignore
        config,
        params,
    )
    return adapter


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="test is too slow for running as a unit test and might be blocked by a rate limiter"
)
async def test_adapter_executes():
    FunctionCall.set_allow_outside_block()
    params = LoadEra5ModelDataParams(
        variables=["u10m"], selection={"time": "2022-09-06T12:00"}
    )
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert isinstance(result[0], xarray.Dataset)
    ds = result[0]

    # TODO: check variables/dims, compare with other loaders
    assert len(ds.variables) == 1 + 5
    assert "u10m" in ds


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

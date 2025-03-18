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
from dfm.api.xarray import OpenDataset as OpenDatasetParams
from dfm.config.common import FsspecConf
from dfm.config.adapter.xarray import OpenDataset as OpenDatasetConfig
from dfm.service.execute.adapter.xarray import OpenDataset as OpenDatasetAdapter
from dfm.service.common.exceptions import DataError
from dfm.api.discovery import SingleFieldAdvice
from dfm.service.execute.discovery import AdviceBuilder

from dfm.config.provider import FsspecProvider as FsspecProviderConfig
from dfm.service.execute.provider import FsspecProvider

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


def create_provider():
    return FsspecProvider(
        provider="testprovider",
        site=None,  # type: ignore
        config=FsspecProviderConfig(
            fsspec_conf=FsspecConf(protocol="file", base_url="tests/")
        ),
        secrets=None,
    )


def create_adapter(params):
    config = OpenDatasetConfig(
        base_url="files",
        filetype="zarr",
    )
    adapter = OpenDatasetAdapter(
        MockDfmRequest(this_site="here"), create_provider(), config, params
    )
    return adapter


@pytest.mark.asyncio
async def test_adapter_executes():
    FunctionCall.set_allow_outside_block()
    params = OpenDatasetParams(file="graf/out/iteration_1.zarr")
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert isinstance(result[0], xarray.Dataset)


@pytest.mark.asyncio
async def test_adapter_only_accepts_correct_filetypes():
    FunctionCall.set_allow_outside_block()
    params = OpenDatasetParams(file="graf/out/iteration_1.netcdf")
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    with pytest.raises(DataError):
        result = []
        async for r in await adapter.get_or_create_stream():
            result.append(r)


@pytest.mark.asyncio
@pytest.mark.skip(reason="As Adviseable isn't supported, from what I can tell")
async def test_discovery():
    FunctionCall.set_allow_outside_block()
    params = OpenDatasetParams.as_adviseable()
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)

    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    print(advice)
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.has_good_options()
    assert advice.field == "file"
    assert "iteration_1.zarr" in str(advice.value)

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
import shutil

from tests.common import MockAdapter
from dfm.api import FunctionCall
from dfm.config.common import FsspecConf
from dfm.api.xarray import WriteToZarr as WriteToZarrParams
from dfm.config.adapter.xarray import WriteToZarr as WriteToZarrConf
from dfm.service.execute.adapter.xarray import WriteToZarr

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


@pytest.mark.asyncio
async def test_adapter_executes():
    # clean up old tests, if necessary
    testfile = "tests/files/testoutputs/test.zarr"
    if os.path.exists(testfile) and os.path.isdir(testfile):
        shutil.rmtree(testfile)

    # load the dataset we want to store
    url = "tests/files/graf/out/iteration_1.zarr"
    ds = xarray.open_dataset(url, engine="zarr")
    dataset = MockAdapter([ds])

    # create adapter
    config = WriteToZarrConf(
        base_url="files/testoutputs",
    )
    FunctionCall.set_allow_outside_block()
    params = WriteToZarrParams(dataset=dataset.node_id, file="test.zarr")
    FunctionCall.unset_allow_outside_block()
    adapter = WriteToZarr(
        MockDfmRequest(this_site="here"),
        create_provider(),
        config,
        params,
        dataset,  # type: ignore
    )

    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    # the function should return only the relative name, not the fully qualified name
    assert result[0] == "test.zarr"

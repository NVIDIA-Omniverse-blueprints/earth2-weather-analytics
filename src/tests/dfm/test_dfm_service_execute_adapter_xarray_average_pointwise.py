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
from tests.common import MockAdapter
from dfm.api import FunctionCall
from dfm.api.xarray import AveragePointwise as AveragePointwiseParams
from dfm.service.execute.adapter.xarray import AveragePointwise

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_adapter_executes():
    FunctionCall.set_allow_outside_block()
    lhs = MockAdapter([xarray.Dataset(dict(foo=[1, 2], bar=("x", [3, 4]), baz=5))])
    rhs = MockAdapter([xarray.Dataset(dict(foo=[5, 4], bar=("x", [3, 2]), baz=1))])
    params = AveragePointwiseParams(lhs=lhs.node_id, rhs=rhs.node_id)
    adapter = AveragePointwise(
        MockDfmRequest(this_site="here"),
        None,  # provider # type: ignore
        None,
        params,
        lhs,  # type: ignore
        rhs,  # type: ignore
    )
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert all(result[0]["bar"].values == [3.0, 3.0])

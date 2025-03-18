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
from dfm.api import FunctionCall
from dfm.api.dfm import GreetMe as GreetMeParams
from dfm.api.dfm import Zip2 as Zip2Params
from dfm.config.adapter.dfm import GreetMe as GreetMeConfig
from dfm.service.execute.adapter.dfm import GreetMe as GreetMeAdapter
from dfm.service.execute.adapter.dfm import Zip2 as Zip2Adapter

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_binary_adapter_zips():
    dfm_request = MockDfmRequest(this_site="here")
    FunctionCall.set_allow_outside_block()
    lhs = GreetMeAdapter(
        dfm_request,
        None,  # provider # type: ignore
        GreetMeConfig(greeting="Hello"),
        GreetMeParams(name="lhs"),
    )
    rhs = GreetMeAdapter(
        dfm_request,
        None,  # provider # type: ignore
        GreetMeConfig(greeting="Hello"),
        GreetMeParams(name="rhs"),
    )

    adapter = Zip2Adapter(
        dfm_request,
        None,  # provider # type: ignore
        params=Zip2Params(lhs=lhs.params.node_id, rhs=rhs.params.node_id),
        lhs=lhs,
        rhs=rhs,
    )
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert result[0] == ("Hello lhs", "Hello rhs")

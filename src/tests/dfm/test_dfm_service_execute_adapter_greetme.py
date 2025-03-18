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
from dfm.config.adapter.dfm import GreetMe as GreetMeConfig
from dfm.service.execute.adapter.dfm import GreetMe

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_adapter_executes():
    FunctionCall.set_allow_outside_block()
    config = GreetMeConfig(greeting="Hello")
    params = GreetMeParams(name="World")
    adapter = GreetMe(
        MockDfmRequest(this_site="here"),
        None,  # provider # type: ignore
        config,
        params,
    )
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert result[0] == "Hello World"

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
from dfm.api import FunctionCall, well_known_id
from dfm.api.dfm import GreetMe as GreetMeParams
from dfm.config.adapter.dfm import GreetMe as GreetMeConfig
from dfm.service.execute.adapter.dfm import SignalAllDone, GreetMe
from dfm.api.dfm import SignalAllDone as SignalAllDoneParams
from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_signal_all_done_waits_for_inputs():
    """Test that SignalAllDone waits for all input adapters to complete before yielding message"""

    # Create some test input adapters
    FunctionCall.set_allow_outside_block()
    inputParams1 = GreetMeParams(name="World 1")
    input1 = GreetMe(
        MockDfmRequest(this_site="here"),
        None,  # provider
        GreetMeConfig(greeting="Hello"),
        inputParams1,
    )

    inputParams2 = GreetMeParams(name="World 2")
    input2 = GreetMe(
        MockDfmRequest(this_site="here"),
        None,  # provider
        GreetMeConfig(greeting="Hello"),
        inputParams2,
    )

    # Create SignalAllDone adapter
    params = SignalAllDoneParams(
        node_id=well_known_id("all_done"),
        after=[inputParams1, inputParams2],
        message="done",
    )
    adapter = SignalAllDone(
        MockDfmRequest(this_site="here"),
        None,  # provider
        None,  # config
        params,
        after=[input1, input2],
    )

    FunctionCall.unset_allow_outside_block()

    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    # Should only yield one message after all inputs complete
    assert len(result) == 1
    assert result[0] == "done"

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
from dfm.api.dfm import Constant
from dfm.api.dfm import AwaitMessage as AwaitMessageParams
from dfm.service.execute.adapter.dfm import AwaitMessage as AwaitMessageAdapter

from tests.common import MockDfmRequest, MockRedis

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_await_message_not_yet_arrived():
    redis = MockRedis()
    dfm_request = MockDfmRequest(this_site="here", redis_client=redis)
    FunctionCall.set_allow_outside_block()
    awm = AwaitMessageAdapter(
        dfm_request,
        None,  # provider # type: ignore
        None,
        AwaitMessageParams(mailbox="my_mailbox", wait_count=1),
    )
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await awm.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert result[0] is None
    # await got rescheduled
    assert len(dfm_request.scheduler_stream) == 1
    body = dfm_request.scheduler_stream[0].execute.body
    assert awm.params.node_id in body
    assert body[awm.params.node_id].mailbox == awm.params.mailbox
    assert body[awm.params.node_id].wait_count == awm.params.wait_count + 1


@pytest.mark.asyncio
async def test_await_message_has_arrived():
    redis = MockRedis()
    dfm_request = MockDfmRequest(this_site="here", redis_client=redis)
    FunctionCall.set_allow_outside_block()
    awm = AwaitMessageAdapter(
        dfm_request,
        None,  # provider # type: ignore
        None,
        AwaitMessageParams(mailbox="my_mailbox"),
    )
    FunctionCall.unset_allow_outside_block()

    await redis.set(f"{dfm_request.request_id}.my_mailbox", "Some Value")

    result = []
    async for r in await awm.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert result[0] is None
    # await's body is enqueued for execution
    assert len(dfm_request.execute_stream) == 1
    body = dfm_request.execute_stream[0].execute.body
    # the original awm node has been replaced with a constant
    assert awm.params.node_id in body
    assert isinstance(body[awm.params.node_id], Constant)
    assert body[awm.params.node_id].value == "Some Value"  # type: ignore

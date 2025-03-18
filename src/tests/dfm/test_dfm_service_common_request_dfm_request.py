# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import datetime
from datetime import timezone
from typing import Dict
import uuid
from pydantic import UUID4
import pytest
from dfm.service.common.request import DfmRequest
from dfm.service.common.message import Package
from dfm.api import FunctionCall
from dfm.api.dfm import PushResponse
from dfm.api.dfm import GreetMe

from tests.common import MockRedis

pytest_plugis = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_dfm_request_creates_streams():
    redis = MockRedis()

    request_id = uuid.uuid4()
    _dfm_request = await DfmRequest(
        this_site="here",
        home_site="home",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )
    assert "ANY.EXECUTE.req.stream" in redis.streams
    assert "ANY.SCHEDULER.req.stream" in redis.streams
    assert "ANY.UPLINK.req.stream" in redis.streams


@pytest.mark.asyncio
async def test_send_remote_heartbeat():
    redis = MockRedis()

    request_id = uuid.uuid4()
    dfm_request = await DfmRequest(
        this_site="here",
        home_site="home",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )
    heartbeat = await dfm_request.send_heartbeat()

    assert len(redis.streams["ANY.UPLINK.req.stream"].past_writes) == 1
    msg = redis.streams["ANY.UPLINK.req.stream"].past_writes[0]
    assert isinstance(msg, dict)
    body = msg["msg"]
    assert isinstance(body, str)
    FunctionCall.set_allow_outside_block()
    package = Package.model_validate_json(body)
    FunctionCall.unset_allow_outside_block()
    assert package.source_site == "here"
    assert package.target_site == "home"
    assert package.job.home_site == "home"
    assert package.job.execute.site == "home"
    push_response = list(package.job.execute.body.values())[0]
    assert isinstance(push_response, PushResponse)
    assert heartbeat == push_response.response.body


@pytest.mark.asyncio
async def test_send_local_heartbeat():
    redis = MockRedis()

    request_id = uuid.uuid4()
    dfm_request = await DfmRequest(
        this_site="here",
        home_site="here",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )
    heartbeat = await dfm_request.send_heartbeat()
    assert f"request:{request_id}" in redis.json_buckets
    state = redis.json_buckets[f"request:{request_id}"]
    assert ".responses" in state
    responses = state[".responses"]
    assert len(responses) == 1
    print(responses)
    assert heartbeat.model_dump() == responses[0]["body"]  # type: ignore


@pytest.mark.asyncio
async def test_remote_schedule_body_delayed():
    redis = MockRedis()

    request_id = uuid.uuid4()
    dfm_request = await DfmRequest(
        this_site="here",
        home_site="home",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )

    FunctionCall.set_allow_outside_block()
    gm = GreetMe(name="James")
    body: Dict[UUID4, FunctionCall] = {gm.node_id: gm}
    FunctionCall.unset_allow_outside_block()

    deadline = datetime.datetime.now(timezone.utc) + datetime.timedelta(days=1)

    await dfm_request.schedule_body(
        target_site="there", node_id=None, body=body, deadline=deadline
    )

    outbox = redis.streams["ANY.UPLINK.req.stream"]
    assert len(outbox.past_writes) == 1
    string = str(outbox.past_writes)
    assert "dfm.api.dfm.GreetMe" in string
    assert '"target_site":"there"' in string


@pytest.mark.asyncio
async def test_remote_schedule_body_immediate():
    redis = MockRedis()

    request_id = uuid.uuid4()
    dfm_request = await DfmRequest(
        this_site="here",
        home_site="home",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )

    FunctionCall.set_allow_outside_block()
    gm = GreetMe(name="James")
    body: Dict[UUID4, FunctionCall] = {gm.node_id: gm}
    FunctionCall.unset_allow_outside_block()

    # in the past!
    deadline = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)

    await dfm_request.schedule_body(
        target_site="there", node_id=None, body=body, deadline=deadline
    )

    outbox = redis.streams["ANY.UPLINK.req.stream"]
    assert len(outbox.past_writes) == 1
    string = str(outbox.past_writes)
    assert "dfm.api.dfm.GreetMe" in string
    assert '"target_site":"there"' in string


@pytest.mark.asyncio
async def test_local_schedule_body_delayed():
    redis = MockRedis()

    request_id = uuid.uuid4()
    dfm_request = await DfmRequest(
        this_site="here",
        home_site="home",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )

    FunctionCall.set_allow_outside_block()
    gm = GreetMe(name="James")
    body: Dict[UUID4, FunctionCall] = {gm.node_id: gm}
    FunctionCall.unset_allow_outside_block()

    deadline = datetime.datetime.now(timezone.utc) + datetime.timedelta(days=1)

    await dfm_request.schedule_body(
        target_site="here", node_id=None, body=body, deadline=deadline
    )

    exec_stream = redis.streams["ANY.SCHEDULER.req.stream"]
    assert len(exec_stream.past_writes) == 1
    print(exec_stream.past_writes)
    string = str(exec_stream.past_writes)
    assert "dfm.api.dfm.GreetMe" in string
    assert '"home_site":"home"' in string


@pytest.mark.asyncio
async def test_local_schedule_body_immediate():
    redis = MockRedis()

    request_id = uuid.uuid4()
    dfm_request = await DfmRequest(
        this_site="here",
        home_site="home",
        request_id=request_id,
        redis_client=redis,  # type: ignore
    )

    FunctionCall.set_allow_outside_block()
    gm = GreetMe(name="James")
    body: Dict[UUID4, FunctionCall] = {gm.node_id: gm}
    FunctionCall.unset_allow_outside_block()

    # in the past!
    deadline = datetime.datetime.now(timezone.utc) - datetime.timedelta(days=1)

    await dfm_request.schedule_body(
        target_site="here", node_id=None, body=body, deadline=deadline
    )

    exec_stream = redis.streams["ANY.EXECUTE.req.stream"]
    assert len(exec_stream.past_writes) == 1
    string = str(exec_stream.past_writes)
    assert "dfm.api.dfm.GreetMe" in string
    assert '"home_site":"home"' in string

#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


"""
Test(s) for k8s Process service
"""
import json
import os
import pytest
import uuid

from datetime import datetime, timezone
from unittest.mock import patch

from fakeredis import FakeRedis
from fastapi.testclient import TestClient
from redis.commands.json.path import Path

import dfm
from dfm.api import Process
from dfm.api.dfm import Execute, GreetMe
from dfm.api.response import (
    Response,
    ValueResponse,
    ErrorResponse,
    StatusResponse,
    HeartbeatResponse,
)
from dfm.service.common.message import Job

### Plumbing ###

# Disable OTEL and set env configuration before importing service code
env = {
    "TRACE_TO_CONSOLE": "false",
    "SERVICE_LOGGING_ENABLE_JSON": "false",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_TRACES_EXPORTER": "none",
    "K8S_PROCESS_SITE_NAME": "localhost",
    "K8S_PROCESS_USE_FAKE_REDIS": "true",
    "DFM_AUTH_METHOD": "none",
}
for k, v in env.items():
    os.environ[k] = v

from k8s.process.process_fastapi import app, fake_redis_server  # noqa: E402


@pytest.fixture
def test_client():
    with TestClient(app) as client:
        yield client


@pytest.fixture
def redis_client():
    redis_client = FakeRedis(decode_responses=True, server=fake_redis_server)
    yield redis_client
    redis_client.flushall()


### Tests ###


def test_get_status(test_client):
    """
    Check if /status endpoint returns expected response (which currently is always "OK")
    """
    response = test_client.get("/status")
    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
    }


def test_get_version(test_client):
    """
    Check if /version endpoint returns expected response (version from VERSION.md file)
    """
    response = test_client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"version": dfm.__version__, "name": "DFM Process"}


@pytest.mark.skip(
    reason="Failing with RuntimeError: No surrounding Process or block context found."
)
def test_process_request(test_client, redis_client):
    """
    Test creation of request object
    """
    request = Process(
        site="localhost",
        execute=Execute(site="localhost", body={uuid.uuid4(): GreetMe(name="Test")}),
    )
    r = test_client.post("/process", data=request.model_dump_json())
    assert r.status_code == 200
    # Make sure we received a well-formed request id uuid
    request_id = r.json()["request_id"]
    assert uuid.UUID(request_id)
    # Make sure service wrote request data to Redis
    rj = redis_client.json()
    entry = rj.get(f"request:{request_id}")
    assert entry["request_id"] == request_id
    assert entry["body"] == json.loads(request.model_dump_json())
    # Make sure correct message was sent to Execute service
    expected_msg = Job(
        home_site="localhost", request_id=request_id, execute=request.execute
    )
    channel_name = app.state.execute_channel.name + ".stream"
    assert redis_client.xlen(channel_name) == 1
    m = redis_client.xrange(channel_name)
    assert len(m) == 1
    msg = Job.model_validate_json(m[0][1]["msg"])
    assert msg == expected_msg


@pytest.mark.skip(
    reason="Failing with RuntimeError: No surrounding Process or block context found."
)
def test_process_request_with_deadline(test_client, redis_client):
    """
    Test creation of request object with a deadline - the difference
    is that the request should go to scheduler queue instead of execute queue.
    """
    request = Process(
        site="localhost",
        deadline=datetime(2050, 1, 1, tzinfo=timezone.utc),
        execute=Execute(site="localhost", body={uuid.uuid4(): GreetMe(name="Test")}),
    )
    r = test_client.post("/process", data=request.model_dump_json())
    assert r.status_code == 200
    # Make sure we received a well-formed request id uuid
    request_id = r.json()["request_id"]
    assert uuid.UUID(request_id)
    # Make sure service wrote request data to Redis
    rj = redis_client.json()
    entry = rj.get(f"request:{request_id}")
    assert entry["request_id"] == request_id
    assert entry["body"] == json.loads(request.model_dump_json())
    # Make sure correct message was sent to Execute service
    expected_msg = Job(
        home_site="localhost",
        deadline=datetime(2050, 1, 1, tzinfo=timezone.utc),
        request_id=request_id,
        execute=request.execute,
    )
    channel_name = app.state.scheduler_channel.name + ".stream"
    assert redis_client.xlen(channel_name) == 1
    m = redis_client.xrange(channel_name)
    assert len(m) == 1
    msg = Job.model_validate_json(m[0][1]["msg"])
    assert msg == expected_msg


@pytest.mark.skip(
    reason="Failing with RuntimeError: No surrounding Process or block context found."
)
def test_process_request_with_invalid_deadline(test_client):
    """
    Test creation of request object with invalid deadline (lacking timezone information).
    This should fail with 422 error code.
    """
    request = Process(
        site="localhost",
        deadline=datetime(2050, 1, 1),
        execute=Execute(site="localhost", body={uuid.uuid4(): GreetMe(name="Test")}),
    )
    r = test_client.post("/process", data=request.model_dump_json())
    assert r.status_code == 422
    assert r.json()["detail"] == "Deadline requires time zone information"


@pytest.mark.skip
def test_malformed_process_request(test_client):
    """
    Hmmm... This should fail but it doesn't because Process has enough
    default values to be created even from that?
    """
    rj = {"invalid": "request"}
    r = test_client.post("/process", data=json.dumps(rj))  # noqa: F841


def test_get_responses_unknown_id(test_client, redis_client):
    """
    Ask about responses for a random id - in an empty database
    this will not exist, so we expect 404
    """
    request_id = str(uuid.uuid4())
    r = test_client.get(f"/request/responses/{request_id}")
    assert r.status_code == 404
    assert r.json()["detail"] == f"Request {request_id} not found"


def test_get_responses_empty(test_client, redis_client):
    """
    Query for responses while no responses are available
    """
    request_id = str(uuid.uuid4())
    redis_client.json().set(
        f"request:{request_id}", Path.root_path(), {"responses": []}
    )
    ret = test_client.get(f"/request/responses/{request_id}")
    assert ret.status_code == 204


def prepare_test_responses(
    redis_client: FakeRedis, count: int, mixed: bool = False
) -> tuple[str, list[Response], list[dict]]:
    request_id = str(uuid.uuid4())
    responses = []
    for i in range(count):
        if mixed and i % 4 == 1:
            responses.append(
                Response(
                    body=ErrorResponse(
                        http_status_code=(400 + i),
                        message=f"Test error {i}",
                        traceback=f"Traceback {i}",
                    )
                )
            )
        elif mixed and i % 4 == 2:
            responses.append(
                Response(
                    body=StatusResponse(
                        originating_site=f"site {i}",
                        message=f"Test status {i}",
                    )
                )
            )
        elif mixed and i % 4 == 3:
            responses.append(
                Response(
                    body=HeartbeatResponse(
                        originating_site=f"site {i}",
                    )
                )
            )
        else:
            responses.append(
                Response(
                    body=ValueResponse(
                        value={"number": str(i)},
                    )
                )
            )

    responses_json = [json.loads(r.model_dump_json()) for r in responses]
    redis_client.json().set(
        f"request:{request_id}", Path.root_path(), {"responses": responses_json}
    )
    return request_id, responses_json


def test_get_responses(test_client, redis_client):
    """
    Query for responses when one result is available
    """
    request_id, responses_json = prepare_test_responses(redis_client, 1)
    ret = test_client.get(f"/request/responses/{request_id}")
    assert ret.status_code == 200
    assert responses_json == ret.json()


def test_get_responses_many(test_client, redis_client):
    """
    Query for responses when many responses are available - get all
    """
    RESPONSE_COUNT = 100
    request_id, responses_json = prepare_test_responses(redis_client, RESPONSE_COUNT)
    ret = test_client.get(f"/request/responses/{request_id}")
    assert ret.status_code == 200
    assert responses_json == ret.json()


def test_get_responses_many_paged(test_client, redis_client):
    """
    Query for responses when many responses are available - get in pages
    """
    PAGE_SIZE = 15
    RESPONSE_COUNT = 100
    request_id, responses_json = prepare_test_responses(redis_client, RESPONSE_COUNT)
    for page in range(int(RESPONSE_COUNT / PAGE_SIZE) + 1):
        ret = test_client.get(
            f"/request/responses/{request_id}?index={page * PAGE_SIZE}&size={PAGE_SIZE}"
        )
        assert ret.status_code == 200
        assert responses_json[page * PAGE_SIZE : (page + 1) * PAGE_SIZE] == ret.json()


def test_get_responses_many_paged_beyond(test_client, redis_client):
    """
    Query for responses when many responses are available - try to get page
    beyond currently available responses.
    """
    PAGE_SIZE = 15
    RESPONSE_COUNT = 100
    request_id, _ = prepare_test_responses(redis_client, RESPONSE_COUNT)
    ret = test_client.get(
        f"/request/responses/{request_id}?index={RESPONSE_COUNT + 1}&size={PAGE_SIZE}"
    )
    assert ret.status_code == 204


def test_get_responses_many_paged_beyond_and_in(test_client, redis_client):
    """
    Query for responses when many responses are available - try to get page
    beyond currently available responses.
    """
    PAGE_SIZE = 15
    RESPONSE_COUNT = 100
    request_id, _ = prepare_test_responses(redis_client, RESPONSE_COUNT)
    ret = test_client.get(
        f"/request/responses/{request_id}?index={RESPONSE_COUNT}&size={PAGE_SIZE}"
    )
    assert ret.status_code == 204
    # Now, let's add one more result and read the same page again - we should succeed.
    one_more_response = Response(
        body=ValueResponse(value={"number": str(RESPONSE_COUNT)})
    )
    one_more_json = json.loads(one_more_response.model_dump_json())
    redis_client.json().arrappend(f"request:{request_id}", "$.responses", one_more_json)
    ret = test_client.get(
        f"/request/responses/{request_id}?index={RESPONSE_COUNT}&size={PAGE_SIZE}"
    )
    assert ret.status_code == 200


def test_get_responses_exception(test_client, redis_client):
    """
    Check that we can correctly handle an exception in data validation.
    """
    request_id, _ = prepare_test_responses(redis_client, 1)
    with patch(
        "k8s.process.process_fastapi.Response.model_validate", autospec=True
    ) as mvm:
        mvm.side_effect = TypeError("Test exception")
        ret = test_client.get(f"/request/responses/{request_id}")
        assert ret.status_code == 500
        assert ret.json()["detail"] == "Test exception"


def test_get_responses_mixed_types(test_client, redis_client):
    """
    Query for responses when many responses are available - get all
    """
    RESPONSE_COUNT = 100
    request_id, responses_json = prepare_test_responses(
        redis_client, RESPONSE_COUNT, mixed=True
    )
    ret = test_client.get(f"/request/responses/{request_id}")
    assert ret.status_code == 200
    assert responses_json == ret.json()


def test_get_responses_mixed_types_many_requests(test_client, redis_client):
    """
    Query for responses when many responses are available - get all
    """
    RESPONSE_COUNT = 100
    REQUESTS_COUNT = 10
    # Add all data to the db first
    data = [
        prepare_test_responses(redis_client, RESPONSE_COUNT, mixed=True)
        for i in range(REQUESTS_COUNT)
    ]
    # Now read data and validate
    for i in range(REQUESTS_COUNT):
        request_id, responses_json = data[i]
        ret = test_client.get(f"/request/responses/{request_id}")
        assert ret.status_code == 200
        assert responses_json == ret.json()

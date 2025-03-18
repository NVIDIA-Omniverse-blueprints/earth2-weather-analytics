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
Test(s) for k8s Execute service
"""
import os
import uuid

from typing import AsyncIterator

import fakeredis
import pytest
import pytest_asyncio

from redis import asyncio as redis

from dfm.api.dfm import Execute, GreetMe
from dfm.service.common.pubsub import Channel
from dfm.service.common.message import Job
from dfm.service.common.request import DfmRequest
from unittest.mock import patch, MagicMock, ANY

# Set environment for service initialization
# pylint: disable=wrong-import-position
env = {
    "TRACE_TO_CONSOLE": "false",
    "SERVICE_LOGGING_ENABLE_JSON": "false",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_TRACES_EXPORTER": "none",
    "K8S_EXECUTE_SITE_CONFIG": "tests/files/simple_site_config.yaml",
    "K8S_EXECUTE_SITE_SECRETS": "tests/files/simple_site_secrets.yaml",
}
for k, v in env.items():
    os.environ[k] = v

from k8s.execute.execute_pubsub import ExecuteService  # noqa: E402


@pytest_asyncio.fixture
async def fake_redis_client() -> AsyncIterator[redis.Redis]:
    async with fakeredis.aioredis.FakeRedis(decode_responses=True) as client:
        yield client


@pytest_asyncio.fixture
async def patched_redis(fake_redis_client):
    with patch("redis.asyncio.Redis", return_value=fake_redis_client):
        yield


@pytest_asyncio.fixture
async def execute_service(patched_redis) -> AsyncIterator[ExecuteService]:
    service = await ExecuteService()
    # Set single iteration mode for testing
    service._single_iter = True
    yield service


@pytest_asyncio.fixture
async def dfm_mock() -> AsyncIterator[MagicMock]:
    with patch(
        "k8s.execute.execute_pubsub.Execute.execute", autospec=True
    ) as dfm_execute:
        yield dfm_execute


@pytest.mark.asyncio
async def test_service_object_creation(execute_service):
    assert isinstance(execute_service, ExecuteService)
    assert isinstance(execute_service._execute_channel, Channel)
    assert hasattr(execute_service, "_consumer_id")
    assert not hasattr(execute_service, "_dask.client")
    assert uuid.UUID(execute_service._consumer_id, version=4) is not None
    assert execute_service._redis is not None


@pytest.mark.asyncio
@patch.dict(os.environ, {"K8S_EXECUTE_DASK_ADDRESS": "local"})
@pytest.mark.skip(reason="Moving to per-adapter DASK usage - maybe temporarily")
async def test_service_object_creation_with_local_dask(patched_redis):
    execute_service = await ExecuteService()
    assert isinstance(execute_service, ExecuteService)
    assert isinstance(execute_service._execute_channel, Channel)
    assert hasattr(execute_service, "_consumer_id")
    assert hasattr(execute_service, "_dask_client")
    assert execute_service._dask_client is not None
    assert execute_service._dask_scheduler_address is None
    assert uuid.UUID(execute_service._consumer_id, version=4) is not None
    assert execute_service._redis is not None


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Failing with AssertionError: Expected 'execute' to be called once. Called 0 times."
)
async def test_simple_request(execute_service, dfm_mock: MagicMock):
    job = Job(
        home_site="home.com",
        request_id=uuid.uuid4(),
        execute=Execute(
            site="localhost",
        ),
    )
    await execute_service._execute_channel.publish(job)
    expected = DfmRequest(
        this_site="simple test site",
        home_site=job.home_site,
        request_id=job.request_id,
        redis_client=execute_service._redis,
    )
    await execute_service.run()
    dfm_mock.assert_called_once_with(ANY, expected, job.execute)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Failing with AssertionError: Expected 'execute' to be called once. Called 0 times."
)
async def test_simple_greetme_request(execute_service, dfm_mock: MagicMock):
    job = Job(
        home_site="home.com",
        request_id=uuid.uuid4(),
        execute=Execute(site="localhost", body={uuid.uuid4(): GreetMe(name="Test")}),
    )
    await execute_service._execute_channel.publish(job)
    expected = DfmRequest(
        this_site="simple test site",
        home_site=job.home_site,
        request_id=job.request_id,
        redis_client=execute_service._redis,
    )
    await execute_service.run()
    dfm_mock.assert_called_once_with(ANY, expected, job.execute)


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Failing with AssertionError: Expected 'execute' to be called once. Called 0 times."
)
async def test_execute_exception(execute_service, dfm_mock: MagicMock):
    job = Job(
        home_site="home.com",
        request_id=uuid.uuid4(),
        execute=Execute(site="localhost", body={uuid.uuid4(): GreetMe(name="Test")}),
    )

    def raise_error():
        raise RuntimeError("Test exception")

    dfm_mock.side_effect = raise_error

    await execute_service._execute_channel.publish(job)
    expected = DfmRequest(
        this_site="simple test site",
        home_site=job.home_site,
        request_id=job.request_id,
        redis_client=execute_service._redis,
    )
    await execute_service.run()
    dfm_mock.assert_called_once_with(ANY, expected, job.execute)
    # We expect that the service will not crash even though execute throws.

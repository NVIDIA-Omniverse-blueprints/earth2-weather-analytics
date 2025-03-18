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
Tests for k8s Scheduler service
"""
from datetime import datetime, timedelta
from typing import AsyncIterator
import os
import pytest
import pytest_asyncio
import fakeredis
from redis import asyncio as redis
from dfm.api import well_known_id
from dfm.service.common.pubsub import Channel
from dfm.service.common.message import Job
from unittest.mock import patch
import uuid

# Disable OTEL before importing service code
# pylint: disable=wrong-import-position
env = {
    "TRACE_TO_CONSOLE": "false",
    "SERVICE_LOGGING_ENABLE_JSON": "false",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_TRACES_EXPORTER": "none",
}
for k, v in env.items():
    os.environ[k] = v

from k8s.scheduler.scheduler_pubsub import SchedulerService  # noqa: E402


@pytest_asyncio.fixture
async def fake_redis_client() -> AsyncIterator[redis.Redis]:
    async with fakeredis.aioredis.FakeRedis(decode_responses=True) as client:
        yield client


@pytest_asyncio.fixture
async def patched_redis(fake_redis_client):
    with patch("redis.asyncio.Redis", return_value=fake_redis_client):
        yield


@pytest_asyncio.fixture
async def patched_datetime():
    with patch("k8s.scheduler.scheduler_pubsub.datetime") as dt:
        yield dt


@pytest_asyncio.fixture
async def scheduler_service(patched_redis) -> AsyncIterator[SchedulerService]:
    service = await SchedulerService()
    # Set single iteration mode for testing
    service._single_iter = True
    yield service


@pytest.mark.asyncio
async def test_service_object_creation(scheduler_service):
    assert isinstance(scheduler_service, SchedulerService)
    assert isinstance(scheduler_service._request_channel, Channel)
    assert isinstance(scheduler_service._execute_channel, Channel)
    assert hasattr(scheduler_service, "_consumer_id")
    assert uuid.UUID(scheduler_service._consumer_id, version=4) is not None
    assert scheduler_service._redis is not None


async def enqueue_jobs(
    fake_redis_client, scheduler_service, deadlines: list
) -> list[Job]:
    """
    Enqueue jobs with given deadlines and return sorted list of these jobs
    """
    # Put all jobs into scheduler input stream
    channel = scheduler_service._request_channel
    jobs = []
    for i, deadline in enumerate(deadlines):
        job = Job(request_id=well_known_id(i), home_site="localhost", deadline=deadline)
        jobs.append(job)
        await channel.publish(job)

    sorted_jobs = sorted(jobs, key=lambda o: o.deadline)
    return sorted_jobs


@pytest.mark.asyncio
async def test_scheduling_empty_queue(scheduler_service, fake_redis_client):
    """
    Check basic iteration - when scheduler has nothing to do.
    """
    await scheduler_service.run()
    channel = scheduler_service._execute_channel
    # Check that the output channel is empty
    length = await fake_redis_client.xlen(channel._stream)
    assert length == 0


@pytest.mark.asyncio
async def test_input_schedule_request(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Check simple scheduling - enqueue one job and see if it is correctly added
    to the scheduler queue.
    """
    patched_datetime.now.return_value = datetime(1978, 7, 5, 8, 30)
    job = Job(
        request_id=uuid.uuid4(),
        home_site="localhost",
        deadline=datetime(1978, 7, 5, 8, 31),
        node_id="some_node_id",
    )
    channel = scheduler_service._request_channel
    await channel.publish(job)

    # Run single iteration
    await scheduler_service.input()

    result = await fake_redis_client.zrange("sched-queue", 0, 0, withscores=True)
    assert len(result) == 1
    msg, timestamp = result[0]
    assert msg == job.model_dump_json()
    assert timestamp == datetime(1978, 7, 5, 8, 31).timestamp()


@pytest.mark.asyncio
async def test_input_schedule_many_requests(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Enqueue multiple jobs and see if they are added to the scheduler queue
    in the correct order.
    """
    deadlines = [
        datetime(2024, 5, 16),
        datetime(2024, 7, 18),
        datetime(2023, 1, 6),
        datetime(2026, 12, 31),
        datetime(2024, 5, 16, 11, 3),
        datetime(1982, 7, 26),
        datetime(2050, 9, 28),
    ]
    # Put jobs into scheduler input stream
    sorted_jobs = await enqueue_jobs(fake_redis_client, scheduler_service, deadlines)

    # Make sure that none of the deadlines expired in our virtual clock
    patched_datetime.now.return_value = sorted_jobs[0].deadline - timedelta(days=1)
    # Run iterations
    for _ in deadlines:
        await scheduler_service.input()
    # Now check if the scheduler correctly inserted all jobs into the queue
    result = await fake_redis_client.zrange(
        "sched-queue", 0, len(deadlines) + 1, withscores=True
    )
    assert len(result) == len(sorted_jobs)
    for i, (msg_json, _score) in enumerate(result):
        msg = Job.model_validate_json(msg_json)
        assert msg.home_site == sorted_jobs[i].home_site
        assert msg.request_id == sorted_jobs[i].request_id
        assert msg.deadline == sorted_jobs[i].deadline
        assert msg.is_discovery == sorted_jobs[i].is_discovery
        assert msg.execute.body == sorted_jobs[i].execute.body
        assert msg.execute.api_class == sorted_jobs[i].execute.api_class
        assert msg.execute.provider == sorted_jobs[i].execute.provider
        assert msg.execute.node_id == sorted_jobs[i].execute.node_id
        assert msg.execute.is_output == sorted_jobs[i].execute.is_output
        assert msg.execute.force_compute == sorted_jobs[i].execute.force_compute
        assert msg.execute.site == sorted_jobs[i].execute.site


@pytest.mark.asyncio
async def test_input_expired_job(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Check if received job that already expired is correctly forwarded to execute queue.
    """
    t = datetime(2024, 7, 4, 1, 11)
    job = Job(
        request_id=uuid.uuid4(),
        home_site="localhost",
        deadline=t,
        node_id="some_node_id",
    )
    # Advance our virtual clock to make sure the job is expired
    patched_datetime.now.return_value = t + timedelta(seconds=1)

    # Run scheduler iteration
    channel_in = scheduler_service._request_channel
    await channel_in.publish(job)
    await scheduler_service.input()

    # Make sure nothing has been put into scheduling queue
    result = await fake_redis_client.zrange("sched-queue", 0, 0, withscores=True)

    # Check that the job has been forwarded to the execute channel
    channel_out = scheduler_service._execute_channel
    result = await fake_redis_client.xrange(channel_out._stream)
    assert len(result) == 1
    r = Job.model_validate_json(result[0][1]["msg"])
    assert r.home_site == job.home_site
    assert r.request_id == job.request_id
    assert r.deadline == job.deadline
    assert r.is_discovery == job.is_discovery
    assert r.execute.body == job.execute.body
    assert r.execute.api_class == job.execute.api_class
    assert r.execute.provider == job.execute.provider
    assert r.execute.node_id == job.execute.node_id
    assert r.execute.is_output == job.execute.is_output
    assert r.execute.force_compute == job.execute.force_compute
    assert r.execute.site == job.execute.site


@pytest.mark.asyncio
async def test_input_zero_deadline_job(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Check if a job with invalid (zero) deadline is correctly forwarded to execute queue.
    """
    job = Job(
        request_id=uuid.uuid4(),
        home_site="localhost",
        deadline=0,
        node_id="some_node_id",
    )
    # Shouldn't really matter, but let's set to ensure consistency
    patched_datetime.now.return_value = datetime(2024, 7, 4, 1, 11)

    # Run scheduler iteration
    channel_in = scheduler_service._request_channel
    await channel_in.publish(job)
    await scheduler_service.input()

    # Make sure nothing has been put into scheduling queue
    result = await fake_redis_client.zrange("sched-queue", 0, 0, withscores=True)

    # Check that the job has been forwarded to the execute channel
    channel_out = scheduler_service._execute_channel
    result = await fake_redis_client.xrange(channel_out._stream)
    assert len(result) == 1
    r = Job.model_validate_json(result[0][1]["msg"])
    assert r.home_site == job.home_site
    assert r.request_id == job.request_id
    assert r.deadline == job.deadline
    assert r.is_discovery == job.is_discovery
    assert r.execute.body == job.execute.body
    assert r.execute.api_class == job.execute.api_class
    assert r.execute.provider == job.execute.provider
    assert r.execute.node_id == job.execute.node_id
    assert r.execute.is_output == job.execute.is_output
    assert r.execute.force_compute == job.execute.force_compute
    assert r.execute.site == job.execute.site


@pytest.mark.asyncio
async def test_input_negative_deadline_job(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Check if a job with invalid (negative) deadline is correctly forwarded to execute queue.
    """
    job = Job(
        request_id=uuid.uuid4(),
        home_site="localhost",
        deadline=-100,
        node_id="some_node_id",
    )
    # Shouldn't really matter, but let's set to ensure consistency
    patched_datetime.now.return_value = datetime(2024, 7, 4, 1, 11)

    # Run scheduler iteration
    channel_in = scheduler_service._request_channel
    await channel_in.publish(job)
    await scheduler_service.input()

    # Make sure nothing has been put into scheduling queue
    result = await fake_redis_client.zrange("sched-queue", 0, 0, withscores=True)

    # Check that the job has been forwarded to the execute channel
    channel_out = scheduler_service._execute_channel
    result = await fake_redis_client.xrange(channel_out._stream)
    assert len(result) == 1
    r = Job.model_validate_json(result[0][1]["msg"])
    assert r.home_site == job.home_site
    assert r.request_id == job.request_id
    assert r.deadline == job.deadline
    assert r.is_discovery == job.is_discovery
    assert r.execute.body == job.execute.body
    assert r.execute.api_class == job.execute.api_class
    assert r.execute.provider == job.execute.provider
    assert r.execute.node_id == job.execute.node_id
    assert r.execute.is_output == job.execute.is_output
    assert r.execute.force_compute == job.execute.force_compute
    assert r.execute.site == job.execute.site


@pytest.mark.asyncio
async def test_scheduling_schedule_simple_request(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Enqueue a simple job and see if it is correctly scheduled when the time comes.
    """
    deadlines = [
        datetime(2020, 1, 2, 3, 4, 5),
    ]
    # Put the job into scheduler input stream
    sorted_jobs = await enqueue_jobs(fake_redis_client, scheduler_service, deadlines)

    # Make sure that none of the deadlines expired in our virtual clock
    patched_datetime.now.return_value = sorted_jobs[0].deadline - timedelta(days=1)
    # Run input iterations to allow the scheduler to put jobs into the queue
    for _ in deadlines:
        await scheduler_service.input()

    # Run one iteration
    await scheduler_service.run()
    # Check that no job has been put into execute channel yet
    channel = scheduler_service._execute_channel
    chl = await fake_redis_client.xlen(channel._stream)
    assert chl == 0

    # Advance time to a second after the job deadline
    patched_datetime.now.return_value = sorted_jobs[0].deadline + timedelta(seconds=1)
    # Run one iteration
    await scheduler_service.run()
    # Check that the job has been forwarded to the execute channel
    channel_out = scheduler_service._execute_channel
    result = await fake_redis_client.xrange(channel_out._stream)
    assert len(result) == 1
    r = Job.model_validate_json(result[0][1]["msg"])
    assert r.home_site == sorted_jobs[0].home_site
    assert r.request_id == sorted_jobs[0].request_id
    assert r.deadline == sorted_jobs[0].deadline
    assert r.is_discovery == sorted_jobs[0].is_discovery
    assert r.execute.body == sorted_jobs[0].execute.body
    assert r.execute.api_class == sorted_jobs[0].execute.api_class
    assert r.execute.provider == sorted_jobs[0].execute.provider
    assert r.execute.node_id == sorted_jobs[0].execute.node_id
    assert r.execute.is_output == sorted_jobs[0].execute.is_output
    assert r.execute.force_compute == sorted_jobs[0].execute.force_compute
    assert r.execute.site == sorted_jobs[0].execute.site


@pytest.mark.asyncio
async def test_scheduling_schedule_multiple_requests(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Enqueue a simple job and see if it is correctly scheduled when the time comes.
    """
    deadlines = [
        datetime(2020, 1, 2, 3, 4, 5),
    ]
    # Add more jobs to schedule
    for i in range(1, 10):
        deadlines.append(deadlines[i - 1] + timedelta(seconds=2))

    # Put the jobs into scheduler input stream
    sorted_jobs = await enqueue_jobs(fake_redis_client, scheduler_service, deadlines)

    # Make sure that none of the deadlines expired in our virtual clock
    patched_datetime.now.return_value = sorted_jobs[0].deadline - timedelta(days=1)
    # Run input iterations to allow the scheduler to put jobs into the queue
    for _ in deadlines:
        await scheduler_service.input()

    # Make sure that none of the deadlines expired in our virtual clock
    patched_datetime.now.return_value = sorted_jobs[0].deadline - timedelta(seconds=1)
    # Run one iteration
    await scheduler_service.run()
    # Check that no job has been put into execute channel yet
    channel = scheduler_service._execute_channel
    chl = await fake_redis_client.xlen(channel._stream)
    assert chl == 0

    # Advance time to half a second after each job deadline and iterate
    for deadline in deadlines:
        patched_datetime.now.return_value = deadline + timedelta(seconds=0.5)
        await scheduler_service.run()
    # Check that the jobs has been forwarded to the execute channel
    channel_out = scheduler_service._execute_channel
    results = await fake_redis_client.xrange(channel_out._stream)
    assert len(results) == len(sorted_jobs)
    for j, result in enumerate(results):
        r = Job.model_validate_json(result[1]["msg"])
        assert r.home_site == sorted_jobs[j].home_site
        assert r.request_id == sorted_jobs[j].request_id
        assert r.deadline == sorted_jobs[j].deadline
        assert r.is_discovery == sorted_jobs[j].is_discovery
        assert r.execute.body == sorted_jobs[j].execute.body
        assert r.execute.api_class == sorted_jobs[j].execute.api_class
        assert r.execute.provider == sorted_jobs[j].execute.provider
        assert r.execute.node_id == sorted_jobs[j].execute.node_id
        assert r.execute.is_output == sorted_jobs[j].execute.is_output
        assert r.execute.force_compute == sorted_jobs[j].execute.force_compute
        assert r.execute.site == sorted_jobs[j].execute.site


@pytest.mark.asyncio
async def test_scheduling_schedule_multiple_requests_time_jump(
    scheduler_service, fake_redis_client, patched_datetime
):
    """
    Enqueue a simple job and see if it is correctly scheduled when the time comes.
    """
    deadlines = [
        datetime(2020, 1, 2, 3, 4, 5),
    ]
    # Add more jobs to schedule
    for i in range(1, 10):
        deadlines.append(deadlines[i - 1] + timedelta(seconds=2))

    # Put the jobs into scheduler input stream
    sorted_jobs = await enqueue_jobs(fake_redis_client, scheduler_service, deadlines)

    # Make sure that none of the deadlines expired in our virtual clock
    patched_datetime.now.return_value = sorted_jobs[0].deadline - timedelta(seconds=1)
    # Run input iterations to allow the scheduler to put jobs into the queue
    for _ in deadlines:
        await scheduler_service.input()

    # Run one iteration
    await scheduler_service.run()
    # Check that no job has been put into execute channel yet
    channel = scheduler_service._execute_channel
    chl = await fake_redis_client.xlen(channel._stream)
    assert chl == 0

    # Advance time to half a second after 5th job deadline and iterate
    # as many steps as jobs in the queue
    patched_datetime.now.return_value = deadlines[5] + timedelta(seconds=0.5)
    for _ in deadlines:
        await scheduler_service.run()
    # Check that 6 jobs has been forwarded to the execute channel
    channel_out = scheduler_service._execute_channel
    results = await fake_redis_client.xrange(channel_out._stream)
    assert len(results) == 6
    for j, result in enumerate(results):
        r = Job.model_validate_json(result[1]["msg"])
        assert r.home_site == sorted_jobs[j].home_site
        assert r.request_id == sorted_jobs[j].request_id
        assert r.deadline == sorted_jobs[j].deadline
        assert r.is_discovery == sorted_jobs[j].is_discovery
        assert r.execute.body == sorted_jobs[j].execute.body
        assert r.execute.api_class == sorted_jobs[j].execute.api_class
        assert r.execute.provider == sorted_jobs[j].execute.provider
        assert r.execute.node_id == sorted_jobs[j].execute.node_id
        assert r.execute.is_output == sorted_jobs[j].execute.is_output
        assert r.execute.force_compute == sorted_jobs[j].execute.force_compute
        assert r.execute.site == sorted_jobs[j].execute.site

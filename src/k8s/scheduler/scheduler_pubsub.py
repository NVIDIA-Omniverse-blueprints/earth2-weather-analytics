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
Implementation of Execute service using pubsub interface
"""
import asyncio
import logging
import os
from uuid import uuid4
from datetime import datetime, timezone

import redis.asyncio

from watchfiles import run_process

import dfm
from dfm.api import FunctionCall
from dfm.service.common.logging import getLogger
from dfm.service.common.pubsub import Channel, Service
from dfm.service.common.message import Job


class SchedulerService:
    """
    Represents a Scheduler using pubsub mechanism for communication.
    """

    LOGGER_NAME = "dfm-scheduler"

    def __init__(self) -> None:
        FunctionCall.set_allow_outside_block()
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self._log = getLogger(SchedulerService.LOGGER_NAME)
        self._log.info("Scheduler service starting up.")

        # For testing - allows to tell execution loops to exit at any time
        self._single_iter = False

        # We need unique id to work with pub/sub mechanism
        self._consumer_id = str(uuid4())
        self._log.info("Consumer id: %s", self._consumer_id)

        # Set version information
        self._version = dfm.__version__
        self._log.info("Scheduler service version: %s", self._version)

        redis_host = os.environ.get("K8S_SCHEDULER_REDIS_HOST", "redis")
        redis_port = os.environ.get("K8S_SCHEDULER_REDIS_PORT", "6379")
        redis_db = os.environ.get("K8S_SCHEDULER_REDIS_DB", "0")
        redis_password = os.environ.get("K8S_SCHEDULER_REDIS_PASSWORD", None)
        self._log.info(
            "Connecting to Redis %s:%s db=%s %s",
            redis_host,
            redis_port,
            redis_db,
            "with password" if redis_password else "",
        )
        self._redis = redis.asyncio.Redis(
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
        )
        self._request_channel = None
        self._execute_channel = None
        self._log.info("Initialized, still needs to bring Redis channels up")

    async def _init_async(self):
        """
        Initializes elements that require asynchronous operations
        """
        self._request_channel = await Channel(
            Service.ANY, Service.SCHEDULER, "req", Job, self._redis
        )
        self._execute_channel = await Channel(
            Service.ANY, Service.EXECUTE, "req", Job, self._redis
        )

        self._log.info("Pubsub channels initialized")
        return self

    def __await__(self):
        """
        Allows await SchedulerService()
        """
        return self._init_async().__await__()

    async def input(self):
        """
        Main communication loop - get scheduling requests from pubsub and store in Redis
        """
        self._log.info(
            "Starting listening for requests on %s", self._request_channel.name
        )
        while True:
            msg = await self._request_channel.consume(self._consumer_id)
            if msg:
                self._log.info("Received message: %s", str(msg))
                message_id, job = msg
                request_id = job.request_id
                # logger = getLogger(self.LOGGER_NAME, request_id)
                self._log.info("Processing request %s, job = %s", request_id, str(job))
                job_timestamp = job.deadline.timestamp()
                now_timestamp_utc = datetime.now(timezone.utc).timestamp()
                if job_timestamp <= 0 or job_timestamp <= now_timestamp_utc:
                    # Short circuit - send this guy directly to Execute;
                    # it already expired or the deadline is bogus
                    self._log.info(
                        "Short circuit - sending request %s directly for execution",
                        request_id,
                    )
                    await self._execute_channel.publish(job)
                else:
                    # Store in Redis sorted set
                    await self._redis.zadd(
                        "sched-queue", {job.model_dump_json(): job_timestamp}, lt=True
                    )
                    self._log.info(
                        "Stored job %s for later, timestamp %f, now is %f",
                        request_id,
                        job_timestamp,
                        now_timestamp_utc,
                    )
                # Acknowledge scheduling request
                self._log.info(
                    "Acknowledging scheduling request (msg id %s)", message_id
                )
                await self._request_channel.ack(message_id)
            if self._single_iter:
                break

    async def run(self):
        """
        Main scheduling loop
        """
        self._log.info("Starting scheduler")
        while True:
            result = await self._redis.zrange("sched-queue", 0, 0, withscores=True)
            if result:
                _, deadline = result[0]
                if deadline <= datetime.now(timezone.utc).timestamp():
                    # We now know that we have something that has expired in the queue.
                    # We have to remove the minimal element. It can be the same element
                    # or a different one (e.g. something has been added in the meantime
                    # with shorter deadline), but it doesn't matter - we have at least one
                    # element expired. Grab it form Redis and send to Execute.
                    top_element = await self._redis.zpopmin("sched-queue", 1)
                    serialized_job, timestamp = top_element[0]
                    job = Job.model_validate_json(serialized_job)
                    self._log.info(
                        "Sending job with timestamp %f to Execute: %s",
                        timestamp,
                        serialized_job,
                    )
                    await self._execute_channel.publish(job)

            if self._single_iter:
                break
            # Sleep a bit
            await asyncio.sleep(0.5)  # pragma: no cover


async def async_main():  # pragma: no cover
    """
    Main asynchronous execution function
    """
    service = await SchedulerService()
    input_task = asyncio.create_task(service.input())
    await service.run()
    await input_task


def main():  # pragma: no cover
    """
    Just a wrapper to run async main with watchfiles
    """
    asyncio.run(async_main())


if __name__ == "__main__":  # pragma: no cover
    if os.getenv("DFM_DEV_MODE", "false").lower() in ("true", "1", "yes"):
        while True:
            run_process(".", target=main)
    else:
        main()

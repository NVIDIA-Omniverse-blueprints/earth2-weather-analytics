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
import textwrap
import yaml

import redis.asyncio

from watchfiles import run_process  # type: ignore

# from dask.distributed import Client

import dfm
from dfm.api import FunctionCall
from dfm.service.execute import Execute
from dfm.service.common.logging import getLogger
from dfm.service.common.pubsub import Channel, Service
from dfm.service.common.message import Job
from dfm.service.common.request import DfmRequest


class ExecuteService:
    """
    Represents Execute service with pubsub interface.
    Execute service consumes Job requests and pass them to
    dfm.Execute.
    """

    # pylint: disable=too-many-instance-attributes
    LOGGER_NAME = "dfm-execute"

    def __init__(self) -> None:
        FunctionCall.set_allow_outside_block()
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        self._log = getLogger(ExecuteService.LOGGER_NAME)
        self._log.info("Execute service starting up.")

        # We need unique id to work with pub/sub mechanism
        self._consumer_id = str(uuid4())
        self._log.info("Consumer id: %s", self._consumer_id)

        # For debugging and experimentation
        self._single_iter = False

        # Set version information
        self._version = dfm.__version__
        self._log.info("Execute service version: %s", self._version)

        # Read configuration and create instance of DFM Execute class
        site_config_path = os.environ.get(
            "K8S_EXECUTE_SITE_CONFIG", "../../tests/files/simple_site_config.yaml"
        )
        site_secrets_path = os.environ.get("K8S_EXECUTE_SITE_SECRETS", "")
        # How do we want to shorten long log lines?
        self._short = 120

        # Config is mandatory
        self._log.info("Reading configuration from %s", site_config_path)
        with open(site_config_path, encoding="utf-8") as f:
            self._site_config = yaml.safe_load(f)
        # But we can have no secrets
        self._site_secrets = None
        if site_secrets_path:
            self._log.info("Reading secrets from %s", site_secrets_path)
            with open(site_secrets_path, encoding="utf-8") as f:
                self._site_secrets = yaml.safe_load(f)

        # # Get the Dask scheduler address
        # dask_scheduler_address = os.environ.get("K8S_EXECUTE_DASK_ADDRESS")
        # if dask_scheduler_address:
        #     if dask_scheduler_address == "local":
        #         dask_scheduler_address = None
        #     self._dask_scheduler_address = dask_scheduler_address
        #     self._log.info("Connecting to Dask %s", self._dask_scheduler_address)
        #     self._dask_client = Client(self._dask_scheduler_address)

        redis_host = os.environ.get("K8S_EXECUTE_REDIS_HOST", "redis")
        redis_port = int(os.environ.get("K8S_EXECUTE_REDIS_PORT", "6379"))
        redis_db = os.environ.get("K8S_EXECUTE_REDIS_DB", "0")
        redis_password = os.environ.get("K8S_EXECUTE_REDIS_PASSWORD", None)
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
        self._execute_channel = None

        self._log.info("Initialized, still needs to bring Redis channels up")

    async def _init_async(self):
        """
        Initializes elements that require asynchronous operations
        """
        self._execute_channel = (
            await Channel(  # pylint: disable=attribute-defined-outside-init
                Service.ANY, Service.EXECUTE, "req", Job, self._redis
            )
        )
        self._log.info("Pubsub channel(s) initialized")
        return self

    def __await__(self):
        """
        Allows await ExecuteService()
        """
        return self._init_async().__await__()

    async def run(self):
        """
        Main execution loop - get requests from pubsub/database and execute them.
        """
        self._log.info("Starting serving requests")
        while True:
            assert self._execute_channel
            msg = await self._execute_channel.consume(self._consumer_id)
            if msg:
                self._log.info(
                    "Received message: %s", textwrap.shorten(str(msg), self._short)
                )
                message_id, job = msg
                assert isinstance(job, Job)
                # Create an instance of execute service to handle the request
                dfm_execute = Execute(self._site_config, self._site_secrets)

                # Acknowledge right away - we don't want to keep the request in the queue for
                # the whole processing time, since it can takes week and if we die during that
                # time, the user will have to retry.
                assert self._execute_channel
                await self._execute_channel.ack(message_id)
                dfm_request = await DfmRequest(
                    this_site=dfm_execute.site.config.site,
                    home_site=job.home_site,
                    request_id=job.request_id,
                    redis_client=self._redis,
                )
                log = getLogger(ExecuteService.LOGGER_NAME, dfm_request)
                log.info(
                    "Processing request %s, home_site=%s",
                    dfm_request.request_id,
                    dfm_request.home_site,
                )
                try:
                    log.info(
                        "Found job data: %s", textwrap.shorten(str(job), self._short)
                    )
                    # run discovery
                    if job.is_discovery:
                        response = await dfm_execute.discover(dfm_request, job.execute)
                        await dfm_request.send_response(None, response)
                    # or execute pipeline
                    else:
                        # Do actual work here
                        async for _heartbeat in await dfm_execute.execute(
                            dfm_request, job.execute
                        ):
                            log.info(
                                "Received heartbeat for request %s",
                                dfm_request.request_id,
                            )  # pragma: no cover
                    log.info(
                        "Finished processing of request %s", dfm_request.request_id
                    )
                except Exception as ex:  # pylint: disable=broad-exception-caught
                    log.error(
                        "Error while processing request %s: %s",
                        dfm_request.request_id,
                        ex,
                    )
            # if running in test mode - bail out
            if self._single_iter:
                break


async def async_main():  # pragma: no cover
    """
    Entrypoint for asynchronous execution
    """
    service = await ExecuteService()
    await service.run()


def main():  # pragma: no cover
    """
    Just a wrapper to convert from sync run_process to async
    """
    asyncio.run(async_main())


if __name__ == "__main__":  # pragma: no cover
    if os.getenv("DFM_DEV_MODE", "false").lower() in ("true", "1", "yes"):
        while True:
            run_process(".", target=main)
    else:
        main()

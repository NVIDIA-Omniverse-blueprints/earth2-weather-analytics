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
Implementation of Execute service
"""
import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple
from pydantic import UUID4, JsonValue, ValidationError

from dfm.service.common.request import DfmRequest

from dfm.api.dfm import Execute as ExecuteParams
from dfm.api.response import HeartbeatResponse
from dfm.api.discovery import (
    DiscoveryResponse,
    BranchFieldAdvice,
    SingleFieldAdvice,
    EdgeT,
)

from dfm.service.common.logging import getLogger
from dfm.service.common.exceptions import ServerError

from dfm.config import SiteConfig
from dfm.secrets import SiteSecrets
from dfm.service.execute.compiler import (
    pipeline_dict_to_adapter_graph,
    pipeline_dict_to_discovery_adapters,
)
from dfm.service.execute.adapter import Stream, Adapter
from dfm.service.execute.discovery import AdviceBuilder
from ._site import Site


class Execute:
    """
    The Execute service is responsible for executing functions.

    Fields:
        _site: The site that the Execute service is running on.
    """

    def __init__(self, config_yaml: Dict, secrets_yaml: Optional[Dict] = None) -> None:
        """
        Initialize the Execute service.

        Args:
            config_yaml: The configuration for the site.
            secrets_yaml: The secrets for the site.

        Raises:
            ServerError: If the site config and secrets cannot be parsed.
        """
        try:
            site_config = SiteConfig.model_validate(config_yaml)
            site_secrets = (
                SiteSecrets.model_validate(secrets_yaml) if secrets_yaml else None
            )
            self._site = Site(site_config=site_config, site_secrets=site_secrets)
        except ValidationError as e:
            raise ServerError("Cannot parse site config and secrets") from e

    @property
    def site(self) -> Site:
        return self._site

    async def _stream_results_as_available(
        self,
        dfm_request: DfmRequest,
        streams: List[Stream],
        heartbeat: float,
        logger: logging.LoggerAdapter,
    ) -> AsyncIterator[HeartbeatResponse]:
        """
        Pumps the leaves for the results. The adapters will call dfm_request.send_XYZ to
        send responses directly. This function will only return heartbeats (if any), in case
        the caller needs that.
        """

        tasks_before = asyncio.all_tasks()

        def create_await_next_task(stream_iterator) -> "asyncio.Task[Any]":
            """An async generator that interleaves the streams and returns the results as they
            become available in any order."""

            async def await_next_task():
                return await anext(stream_iterator)  # noqa: F821

            loop = asyncio.get_event_loop()
            return loop.create_task(await_next_task())

        try:
            # each task always awaits a single next value from the stream and then stops
            # For the subsequent values, we'll then create a new task
            iterators = [aiter(stream) for stream in streams]  # noqa: F821
            # map from iterator to the next task, so we can find one from the other
            tasks = {
                create_await_next_task(iterator): iterator for iterator in iterators
            }
            logger.info(
                "execute._stream_results_as_available() starting with %s tasks",
                len(tasks),
            )
            while tasks:
                done, _pending = await asyncio.wait(
                    tasks.keys(), return_when=asyncio.FIRST_COMPLETED, timeout=heartbeat
                )
                if not done:
                    # woke up from timeout
                    hb = await dfm_request.send_heartbeat()
                    yield hb
                    continue

                logger.debug("execute got %s tasks that are done", len(done))
                for task in done:
                    # "dequeue" task, it's done
                    iterator = tasks[task]
                    del tasks[task]
                    node_id = (
                        iterator.stream.node_id
                    )  # to which node does this iterator belong?
                    try:
                        _result = task.result()
                    except StopAsyncIteration:
                        pass
                    except Exception as e:  # pylint: disable=broad-exception-caught
                        # we give up on this stream if there's an exception
                        logger.debug("task caused an exception during execute")
                        logger.exception(e)
                        await dfm_request.send_error(node_id, e)
                    else:
                        # Iterator isn't done yet schedule the task for the next value
                        logger.debug(
                            "execute task's iterator has more elements, re-scheduling it"
                        )
                        new_task = create_await_next_task(iterator)
                        tasks[new_task] = iterator
        finally:
            # kill all tasks that may still be ongoing
            tasks_after = asyncio.all_tasks()
            for t in tasks_after:
                if t not in tasks_before:
                    logger.info("Killing task %s after Execute.execute() is done", t)
                    t.cancel()
            self._site.close()

    async def execute(
        self, dfm_request: DfmRequest, params: ExecuteParams
    ) -> AsyncIterator[HeartbeatResponse]:
        # Initialize logging
        logger = getLogger(__name__, dfm_request)
        leaves = pipeline_dict_to_adapter_graph(self._site, dfm_request, params.body)
        logger.info("pipeline_dict_to_adapter_graph: %s", str(leaves))
        streams = [await leaf.get_or_create_stream() for leaf in leaves]
        logger.info("streams: %s", str(streams))
        logger.info(
            "Exeute.execute() started working on request %s", dfm_request.request_id
        )
        return self._stream_results_as_available(
            dfm_request, streams, self._site.config.heartbeat_interval, logger
        )

    async def discover(
        self, dfm_request: DfmRequest, params: ExecuteParams
    ) -> DiscoveryResponse:

        pipeline: Dict[UUID4, Adapter | List[Adapter]] = (
            pipeline_dict_to_discovery_adapters(self._site, dfm_request, params.body)
        )
        result: Dict[UUID4, BranchFieldAdvice | SingleFieldAdvice | None] = {}

        for node_id, maybe_adapter_list in pipeline.items():
            if isinstance(maybe_adapter_list, Adapter):
                adapter = maybe_adapter_list
                builder = AdviceBuilder(adapter)
                advice = await builder.generate_advice()
                result[node_id] = advice
            else:
                adapter_list = maybe_adapter_list
                branches: List[Tuple[JsonValue, EdgeT]] = []
                for adapter in adapter_list:
                    builder = AdviceBuilder(adapter)
                    advice = await builder.generate_advice()
                    branches.append((adapter.provider.provider, advice))
                advice = BranchFieldAdvice(field="provider", branches=branches)
                result[node_id] = advice

        response = DiscoveryResponse(advice=result)
        return response

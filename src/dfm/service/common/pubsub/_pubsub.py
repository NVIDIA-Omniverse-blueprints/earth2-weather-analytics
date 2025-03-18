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
Common pub-sub code
"""
from enum import Enum
import time
import json
from typing import Type, Tuple
from pydantic import BaseModel
import redis.asyncio
from redis.exceptions import ResponseError as RedisResponseError
from redis.exceptions import ConnectionError as RedisConnectionError
import textwrap

from ...common.logging import getLogger
from dfm.common import AdviseableBaseModel

log = getLogger("pubsub.common")


class Service(Enum):
    """
    Services in the network.
    """

    ANY = "any"
    PROCESS = "process"
    EXECUTE = "execute"
    UPLINK = "uplink"
    SCHEDULER = "scheduler"


MessageIdT = str


class Channel:
    """
    Represents a pub/sub channel used for communication between services
    """

    # Maximum number of connection failures
    MAX_FAILURES = 15
    SHORT = 120

    def __init__(
        self,
        src: Service,
        dst: Service,
        topic: str,
        message_class: Type[BaseModel],
        redis_client: redis.asyncio.Redis,
    ) -> None:
        """
        Initialize basic channel information
        """
        self._message_class = message_class
        name = ".".join([src.name, dst.name, topic])
        # Allow user to read (or even set) the channel name - it has no meaning
        # other than debugging
        self.name = name
        self._stream = name + ".stream"
        self._group = name + ".group"
        self._log = getLogger(f"pubsub.common.{self._stream}")
        self._redis = redis_client

    async def _init_async(self):
        """
        Initialize elements that require asynchronous operations
        """
        try:
            await self._redis.xgroup_create(
                self._stream, self._group, id="$", mkstream=True
            )
        except RedisResponseError as e:
            if "BUSYGROUP Consumer Group name already exists" in str(e):
                self._log.warning("Consumer group %s already exists", self._group)
            else:
                raise
        return self

    # A nice way to make sure asynchronous initialization,
    # makes it possible to call:
    # ch = await Channel(...)
    def __await__(self):
        return self._init_async().__await__()

    async def publish(self, msg: BaseModel) -> None:
        """
        Post a message with processing request
        """
        if not isinstance(msg, self._message_class):
            raise ValueError(
                f"Cannot publish message of type {msg.__class__.__name__}."
                f" Channel is expecting messages of type {self._message_class}"
            )
        await self._redis.xadd(self._stream, {"msg": msg.model_dump_json()})

    async def consume(self, consumer_id: str) -> Tuple[MessageIdT, BaseModel] | None:
        """
        Read a processing request from the queue and return request id
        """
        failures = 0
        for _ in range(30):
            try:
                # Read just one message from the group. Using a group means that only one consumer
                # will get the message.
                response = await self._redis.xreadgroup(
                    self._group, consumer_id, {self._stream: ">"}, count=1, block=5000
                )
                if response:
                    self._log.info(
                        "Received from %s: %s",
                        self._stream,
                        textwrap.shorten(str(response), Channel.SHORT),
                    )
                    # Since we know we only read one message from the stream,
                    # we can skip looping over received data
                    _, m = response[0]  # type: ignore
                    message_id, message = m[0]
                    message = message["msg"]
                    # parse to json to do discovery check
                    message_dict = json.loads(message)
                    is_discovery = message_dict.get("is_discovery", False)
                    last_value = AdviseableBaseModel.set_allow_advise(is_discovery)
                    job_or_package = self._message_class.model_validate(message_dict)
                    AdviseableBaseModel.set_allow_advise(last_value)
                    return message_id, job_or_package
            except RedisConnectionError as e:
                failures += 1
                if failures >= self.MAX_FAILURES:
                    self._log.error(
                        "Maximum number of connection errors reached (%d)",
                        self.MAX_FAILURES,
                    )
                    # Throw the towel
                    raise e
                self._log.warning(
                    "Connection error while trying to get new request from pubsub (%d/%d)",
                    failures,
                    self.MAX_FAILURES,
                )
                time.sleep(5)  # Retry after 5 seconds
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._log.error(
                    "Could not parse message into a model of type %s. Error was %s",
                    self._message_class.__name__,
                    e,
                )
                raise e
        return None

    async def ack(self, message_id: MessageIdT) -> None:
        """
        Acknowledge completion of handling a message (in other words - processing of a request)
        """
        await self._redis.xack(self._stream, self._group, message_id)

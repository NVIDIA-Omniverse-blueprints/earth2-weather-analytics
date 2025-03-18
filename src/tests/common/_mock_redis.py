# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import asyncio
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel, JsonValue


class MockStream:
    def __init__(self):
        self.next_reads: asyncio.Queue[Tuple[Any, JsonValue]] = asyncio.Queue()
        self.past_writes: List[JsonValue] = []


class MockRedis:
    def __init__(self):
        self.streams: Dict[str, MockStream] = {}
        self.json_buckets: Dict[str, Dict[str, List[JsonValue]]] = {}
        self.buckets = {}

    async def set(self, key: str, value: Any):
        self.buckets[key] = value

    async def get(self, key: str) -> Any:
        return self.buckets.get(key, None)

    async def put_xreadgroup_next_return_value(
        self, stream_name, message_id: Any, value: Any
    ):
        stream = self.streams[stream_name]
        if isinstance(value, BaseModel):
            await stream.next_reads.put((message_id, {"msg": value.model_dump_json()}))
        else:
            await stream.next_reads.put((message_id, {"msg": value}))

    async def xreadgroup(
        self, group, consumer_id, streams_dict, count, block
    ):  # pylint: disable=unused-argument
        assert len(streams_dict) == 1
        stream = self.streams[list(streams_dict.keys())[0]]
        msg_tuple = await stream.next_reads.get()
        print(f"MockRedis.xreadgroup returning msg_tuple {msg_tuple}")
        # the connsume function expects some weird redis structure
        return (("??", (msg_tuple, "??")),)

    async def xgroup_create(
        self, stream: str, group: str, id: str, mkstream: bool
    ):  # pylint: disable=redefined-builtin
        assert id == "$"
        assert stream.endswith(".stream")
        assert group.endswith(".group")
        assert mkstream
        self.streams[stream] = MockStream()

    async def xadd(self, stream, msg: JsonValue):
        assert stream in self.streams
        print(f"Adding msg {msg} to stream {stream}")
        self.streams[stream].past_writes.append(msg)

    async def xack(self, stream, group, message_id):
        print(f"xack(stream={stream}, group={group}, message_id={message_id})")

    def json(self):
        return self

    async def arrappend(self, key, json_key, val):
        if key not in self.json_buckets:
            self.json_buckets[key] = {}
        bucket = self.json_buckets[key]
        if json_key not in bucket:
            bucket[json_key] = []
        array = bucket[json_key]
        array.append(val)

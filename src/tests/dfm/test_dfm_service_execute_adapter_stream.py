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
import uuid
import pytest

from dfm.service.execute.adapter import Stream  # noqa: E402
from dfm.service.common.exceptions import ServerError  # noqa: E402

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_stream_futures_in_order():
    loop = asyncio.get_event_loop()
    f1 = loop.create_future()
    f2 = loop.create_future()

    async def task(f, value, sleep):
        await asyncio.sleep(sleep)
        f.set_result(value)

    loop.create_task(task(f1, 42, 0.1))
    loop.create_task(task(f2, 66, 0))

    stream = Stream.from_futures_in_order(
        "testing", request_id=uuid.uuid4(), node_id=None, futures=[f1, f2]
    )
    stream.start()
    results = []
    async for v in stream:
        results.append(v)

    assert results[0] == 42
    assert results[1] == 66


@pytest.mark.asyncio
async def test_stream_from_async_iterator():

    async def generator():
        for i in range(2):
            yield i
        await asyncio.sleep(0.1)

    stream = Stream.from_async_iterator(
        "testing", request_id=uuid.uuid4(), node_id=None, async_it=generator()
    )
    stream.start()
    results = []
    async for v in stream:
        results.append(v)

    assert results[0] == 0
    assert results[1] == 1


@pytest.mark.asyncio
async def test_stream_filter_errors_if_stream_is_running():

    async def generator():
        for i in range(6):
            yield i
        await asyncio.sleep(0.01)

    filtered = []

    async def keep_even(value) -> bool:
        if value % 2 == 0:
            return True
        else:
            filtered.append(value)
            return False

    stream = Stream.from_async_iterator(
        "testing", request_id=uuid.uuid4(), node_id=None, async_it=generator()
    )
    stream.start()
    with pytest.raises(ServerError):
        stream.add_filter(keep_even)
    # cancel the task, otherwise we get a "cancelled task is still pending" error
    stream.cancel()


@pytest.mark.asyncio
async def test_stream_filter():

    async def generator():
        for i in range(6):
            yield i
        await asyncio.sleep(0.01)

    filtered = []

    async def keep_even(value) -> bool:
        if value % 2 == 0:
            return True
        else:
            filtered.append(value)
            return False

    stream = Stream.from_async_iterator(
        "testing", request_id=uuid.uuid4(), node_id=None, async_it=generator()
    )
    stream.add_filter(keep_even)
    stream.start()
    results = []
    async for v in stream:
        results.append(v)

    assert results[0] == 0
    assert results[1] == 2
    assert results[2] == 4

    assert filtered[0] == 1
    assert filtered[1] == 3
    assert filtered[2] == 5


@pytest.mark.asyncio
async def test_stream_iterators():
    loop = asyncio.get_event_loop()
    f1 = loop.create_future()
    f1.set_result(42)
    stream = Stream.from_futures_in_order(
        "testing", request_id=uuid.uuid4(), node_id=None, futures=[f1]
    )
    stream.start()
    it1 = aiter(stream)  # noqa: F821
    it2 = aiter(stream)  # noqa: F821

    # iteraton
    assert it1.stream == stream
    assert it1._counter == 0  # pylint: disable=protected-access
    assert it2._counter == 0  # pylint: disable=protected-access

    # iteration
    n = await anext(it1)  # noqa: F821
    assert n == 42
    assert it1._counter == 1  # pylint: disable=protected-access
    assert it2._counter == 0  # pylint: disable=protected-access

    # 1 is done
    with pytest.raises(StopAsyncIteration):
        await anext(it1)  # noqa: F821
    assert it1._counter == 2  # pylint: disable=protected-access
    assert it2._counter == 0  # pylint: disable=protected-access

    # advance 2
    n = await anext(it2)  # noqa: F821
    assert it1._counter == 2  # pylint: disable=protected-access
    assert it2._counter == 1  # pylint: disable=protected-access

    # 1 still is done
    with pytest.raises(StopAsyncIteration):
        await anext(it1)  # noqa: F821

    # 2 is now done, too
    with pytest.raises(StopAsyncIteration):
        await anext(it2)  # noqa: F821
    assert it2._counter == 2  # pylint: disable=protected-access

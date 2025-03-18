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
import inspect
from typing import Any, AsyncIterator, Awaitable


class AwaitAsCompleted:
    """
    A AwaitAsCompleted is a class that awaits a list of awaitables as they are completed.
    """

    def __init__(self, awaitables):
        self.awaitables = awaitables


class AwaitInOrder:
    """
    A AwaitInOrder is a class that awaits a list of awaitables in order.
    """

    def __init__(self, awaitables):
        self.awaitables = awaitables


BodyResultT = Awaitable | AsyncIterator | AwaitAsCompleted | AwaitInOrder | Any


async def body_result_to_async_generator(result: BodyResultT) -> AsyncIterator[Any]:
    """
    A body_result_to_async_generator is a function that converts a body result to an async generator.
    """
    if inspect.isasyncgen(result):
        async for res in result:
            yield res
    elif inspect.isawaitable(result):
        res = await result
        yield res
    elif isinstance(result, AwaitInOrder):
        for awaitable in result.awaitables:
            res = await awaitable
            yield res
    elif isinstance(result, AwaitAsCompleted):
        for awaitable in asyncio.as_completed(result.awaitables):
            res = await awaitable
            yield res
    else:
        yield result

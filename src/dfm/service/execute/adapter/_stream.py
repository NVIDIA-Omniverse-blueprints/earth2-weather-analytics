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
from typing import Any, AsyncIterator, Awaitable, Callable, List, Optional
from uuid import UUID
from dfm.service.common.exceptions import ServerError

from dfm.service.common.logging import getLogger


class StreamIterator:
    """
    A StreamIterator is an iterator that iterates over a stream.
    """

    def __init__(self, stream):
        self._stream = stream
        self._counter = 0

    async def __anext__(self):
        if self._counter >= len(self._stream._futures):
            raise StopAsyncIteration()
        future = self._stream._futures[self._counter]
        assert isinstance(future, asyncio.Future)
        self._counter += 1
        result = await future
        return result

    @property
    def stream(self) -> "Stream":
        return self._stream

    def raise_if_exception(self):
        self._stream.raise_if_exception()


class Stream:
    """
    A Stream is a class that encapsulates a list of futures and/or an async generator. The Stream
    maintains a list of Future objects that will contain the generated items. The Stream starts a
    async Task function _start() which will start generating those elements one at a time.
    The interesting part of the stream is that it can be iterated in multiple async methods
    concurrently; each loop will return the same items in the same order for each async task
    (and block if it gets to the element that is still being computed). Stream maintains the list
    of futures which always has an empty 'next' future as the last element,
    which will either retrieve the result, once computed, or the StopAsyncIteration exception,
    signalling the end of stream"""

    def __init__(
        self,
        adapterclass: str,
        request_id: UUID,
        node_id: Optional[UUID],
        async_it: Optional[AsyncIterator] = None,
        futures: Optional[List[asyncio.Future]] = None,
    ):
        """
        output_id -- If the FunctionCall handled by this stream's adapter specified an output_id
                     to recognize the result, this is it
        async_it -- an asynchronous iterator producing the values behind this stream. If None,
                     the stream will only contain the provided futures list.
        futures -- a list of pre-made futures that will be used for the stream. NOTE:
                    currently, you can only give an iterator OR a list of futures, not both
        """

        if async_it and futures:
            raise ServerError(
                "Can only create a stream from either an async_it or a list"
                " of futures, but not both."
            )

        self._node_id = node_id
        self._async_it = async_it
        self._futures: List[asyncio.Future] = futures.copy() if futures else []

        # create the next/sentinel future, in case clients start iterating already
        loop = asyncio.get_event_loop()
        next_future = loop.create_future()
        if async_it is None:
            # user didn't provide a generator, we stop after the futures list
            next_future.set_exception(StopAsyncIteration())

        self._futures.append(next_future)

        # consumers can register callbacks to receive values produced in this stream
        # and filter them out, if needed (i.e. if any callback returns False, then
        # this value will not be outputted by the stream). This allows for bypassing
        # some values, for example, if some elements in a stream have already been cached
        # at the output
        self._filters: List[Callable[[Any], Awaitable[bool]]] = []

        # probably technically not needed, since asyncio isn't preemptive, but just to be
        # future proof
        self._asyncio_lock = asyncio.Lock()

        # start computing the stream
        self.task = None

        self._logger = getLogger(
            f"{self.__class__.__name__} Stream for adapter {adapterclass}", request_id
        )

    def start(
        self,
        stream_done_callback: Optional[Callable[[asyncio.Task[None]], None]] = None,
    ):
        if self.is_running():
            raise ServerError("Tried to start stream that is already running")
        loop = asyncio.get_event_loop()
        self.task = loop.create_task(self._main())
        self.task.add_done_callback(self._task_done_callback)
        if stream_done_callback:
            self.task.add_done_callback(stream_done_callback)

    def is_running(self) -> bool:
        return self.task is not None

    def cancel(self):
        if self.task:
            self.task.cancel()
        self.task = None

    @property
    def futures(self) -> List[asyncio.Future]:
        return self._futures

    @property
    def node_id(self) -> Optional[UUID]:
        return self._node_id

    def add_filter(self, filter_callback: Callable[[Any], Awaitable[bool]]):
        if self.task:
            raise ServerError("Tried to add filter to stream that is already running")
        self._filters.append(filter_callback)

    async def _main(self):
        """This is the 'main thread' of the stream that initiates the async
        computation of the elements. I.e. the stream doesn't wait for a client to pull via
        anext(async_generator) but it will proactively start working
        before the clients ask. This method asyncronously iterates over the generator
        and adds the results to the futures list. There is always exactly one future object more
        in the futures array than what the generator currently produced. This future will either
        retrieve the next result or the final future will contain the StopAsyncIteration future
        """
        # if nothing to generate, we are done
        if not self._async_it:
            # NOTE: currently, a stream can only be created from an iterator OR a futures list
            # We don't have an iterator, therefore we can wait on all the futures before exiting
            # the task. If there were an iterator, there would be an empty future in the last
            # place from the constructor, and waiting would block indefinitely. If we want
            # to support a pre-made list plus an iterator, we'd have to take care of this here
            for f in self._futures:
                if not f.done():
                    await f
            return

        loop = asyncio.get_event_loop()
        next_future = self._futures[-1]
        try:
            self._logger.info("stream._main starts looping adapter.stream_body_wrapper")
            async for value in self._async_it:
                # check that all filters allow this value to be passed on
                # all() also returns True for an empty list
                if all(
                    [await filter_callback(value) for filter_callback in self._filters]
                ):
                    async with self._asyncio_lock:
                        # NOTE: the following code must execute atomically
                        # technically, we probably don't need a lock, but just to be future proof
                        next_future.set_result(value)
                        # create a new sentinel future
                        next_future = loop.create_future()
                        self._futures.append(next_future)
                else:
                    self._logger.info(
                        "stream._main got result but filter prevented adding it to the stream"
                    )
            self._logger.info(
                "stream._main loop is done. Setting StopAsyncIteration in last future"
            )
            # done with the generator
            next_future.set_exception(StopAsyncIteration())
        except StopAsyncIteration as e:
            # an adapter is allowed to raise StopAsyncIteration, we don't
            # raise in this case
            next_future.set_exception(e)
        except Exception as e:
            # setting the exception will make the future "poisonous". Whenever a
            # subsequent adapter touches this future the exception will get raised,
            # until it trickles all the way up to the original caller. Which is what we want
            next_future.set_exception(e)
            raise e

    def _task_done_callback(self, task):
        # just in case, always make sure that there's no unfinished future
        try:
            exception = task.exception()
            if exception:
                self._logger.exception(
                    "Stream's task raised an exception %s", exception
                )
        except asyncio.CancelledError:
            self._logger.error("Stream's task was cancelled")

        for future in self._futures:
            # Note: calling cancel() on a future that's done already is a noop;
            # we we don't try to be too careful here
            future.cancel()

    def raise_if_exception(self):
        assert self.task
        if self.task.done():
            ex = self.task.exception()
            if ex:
                # stream suffered from an exception, aborting early
                raise ex

    def __aiter__(self):
        return StreamIterator(self)

    @classmethod
    def from_async_iterator(
        cls,
        adapterclass: str,
        request_id: UUID,
        node_id: Optional[UUID],
        async_it: AsyncIterator,
    ):
        return Stream(
            adapterclass=adapterclass,
            request_id=request_id,
            node_id=node_id,
            async_it=async_it,
        )

    @classmethod
    def from_futures_in_order(
        cls,
        adapterclass: str,
        request_id: UUID,
        node_id: Optional[UUID],
        futures: List[asyncio.Future],
    ):
        return Stream(
            adapterclass=adapterclass,
            request_id=request_id,
            node_id=node_id,
            futures=futures,
        )

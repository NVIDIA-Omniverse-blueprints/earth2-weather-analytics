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

# -*- coding: utf-8 -*-
import json
import logging
import os
from typing import List, Optional
from uuid import UUID

import aiohttp
import asyncio

from dfm.api import Process, FunctionCall
from dfm.api.response import (
    Response,
    ValueResponse,
    ErrorResponse,
    StatusResponse,
    HeartbeatResponse,
)
from ._common import RequestType, normalize_url


class DfmException(Exception):
    """
    Base exception class for DFM Client errors
    """

    def __init__(self, *args: object) -> None:
        super().__init__(*args)


class ErrorResponseException(DfmException):
    """The exception type raised when calling raise_on_error() and the
    response was an ErrorResponse"""

    def __init__(
        self, obj: ErrorResponse, message: str = "Error response from DFM"
    ) -> None:
        super().__init__(message)
        self._obj = obj
        self._message = message

    def __str__(self):
        return f"{self._message} {str(self._obj)}"


class AsyncResponsesIterator:
    """
    Allows for asynchronous iteration over responses received from a DFM site.
    """

    def __init__(
        self,
        client: "AsyncClient",
        request_id: str,
        stop_node_ids: Optional[UUID | List[UUID]] = None,
        return_errors: bool = True,
        return_statuses: bool = False,
        page_size: int = 10,
    ) -> None:
        self._client = client
        self._request_id = request_id
        self._page_size = page_size
        if isinstance(stop_node_ids, UUID):
            stop_node_ids = [stop_node_ids]
        self._stop_node_ids = set(stop_node_ids) if stop_node_ids else None
        self._return_errors = return_errors
        self._return_statuses = return_statuses
        self._glob_index = 0
        self._cache_index = 0
        self._cache = []
        self._stop_iterator = False

    def __aiter__(self) -> "AsyncResponsesIterator":
        return self

    async def __anext__(self) -> Response | None:
        # If the user asked us to manage stop condition and we have no more
        # responses to wait for - bail out.
        if self._stop_iterator:
            raise StopAsyncIteration
        # Fetch current request status - what state is it in and how many responses
        # are currently available.
        cached = len(self._cache)
        if not cached:
            # We have nothing cached, so we have to grab something from the server... if we can.
            cache = await self._client.paged_responses(
                self._request_id, self._glob_index, self._page_size
            )
            if cache:
                self._cache = cache
            else:
                self._cache.clear()
            self._cache_index = 0
            cached = len(self._cache)
        if cached and self._cache_index < cached:
            # We have some cached responses, let's yield from the cache first
            r = self._cache[self._cache_index]
            self._cache_index += 1
            self._glob_index += 1
            if self._cache_index >= cached:
                # We served all we had in cache - reset cache to grab more data in next iteration
                self._cache.clear()
            validated = Response.model_validate(r)
            if (
                isinstance(validated.body, ValueResponse)
                and self._stop_node_ids is not None
            ):
                if validated.node_id in self._stop_node_ids:
                    self._stop_node_ids.remove(validated.node_id)
                    self._stop_iterator = not self._stop_node_ids
            if isinstance(validated.body, ErrorResponse) and not self._return_errors:
                return None
            is_status = isinstance(validated.body, StatusResponse) or isinstance(
                validated.body, HeartbeatResponse
            )
            if is_status and not self._return_statuses:
                return None
            return validated
        # Just return none and let the clients decide how to handle that
        return None


class AsyncClient:
    """
    Asynchronous client for DFM service.
    """

    def __init__(
        self,
        url: str = "http://localhost:8080",
        retries: int = 10,
        timeout: float = 60,
        logger: Optional[logging.Logger] = None,
        backoff: float = 1.0,
    ) -> None:
        """
        Parameters:
        url - URL of the DFM environment
        retries - number of retries when calling DFM API
        timeout - timeout for each http call (in seconds)
        logger - logger to use
        backoff - backoff factor for retries (in seconds)
        """
        if logger:
            self._log = logger
        else:
            # Setup a noop logger to keep logging statements in the code
            # but keep things quite
            self._log = logging.getLogger(__name__)
            self._log.handlers = [logging.NullHandler()]

        self._url = normalize_url(url)
        # Initialize retries mechanism
        self._retries = retries
        self._timeout = timeout
        self._backoff = backoff
        # Session should be created by using the client as a context manager
        self._session = None
        # Store authentication credentials if provided
        self._secret = os.environ.get("DFM_AUTH_API_KEY", "")
        # Just to make pydantic happy
        FunctionCall.set_allow_outside_block()

    async def __aenter__(self) -> "AsyncClient":
        """
        The recommended way of using the client is to use it as a context manager
        to effectively manage resources cleanup. Otherwise calling AsyncClient.close()
        method must be handled by the user.
        """
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """
        Closes active session when using client as a context manager
        """
        await self.close()

    async def close(self) -> None:
        """
        Cleans up session resources.
        """
        if self._session:
            await self._session.close()

    async def version(self) -> str:
        """
        Returns DFM environment version as a string.
        """
        r = await self._http_request("/version")
        return r["version"]

    async def paged_responses(
        self, request_id: str, index: int = 0, size: int = 0
    ) -> List[Response] | None:
        """
        Returns responses starting at provided index. If requested size is not provided (or is 0),
        the function returns all responses starting from index. If size is provided and is smaller than
        the number of available responses, only available ones are returned.
        """
        responses = await self._http_request(
            f"/request/responses/{request_id}?index={index}&size={size}"
        )
        if not responses:
            # Indicates 204, which simply means we have to try again, since no responses are ready yet
            return None
        return [Response.model_validate(r) for r in responses]

    async def all_responses(self, request_id: str) -> List[Response] | None:
        """
        Returns all available responses for given request.
        """
        response = await self._http_request(f"/request/responses/{request_id}")
        if not response:
            return None
        return [Response.model_validate(r) for r in response]

    def responses(
        self,
        request_id: str,
        stop_node_ids: UUID | List[UUID] | None = None,
        return_errors: bool = True,
        return_statuses: bool = False,
    ) -> AsyncResponsesIterator:
        """
        Returns an iterator that allows for fetching all responses (currently available and future).
        The iterator will return all available responses one by one or block and wait until a response is available.
        """
        return AsyncResponsesIterator(
            self, request_id, stop_node_ids, return_errors, return_statuses
        )

    async def process(self, pipeline: Process) -> str:
        """
        Initiates request processing and returns request id that identifies the request (as a string).
        """
        response = await self._http_request(
            "/process",
            body=json.loads(pipeline.model_dump_json()),
            rtype=RequestType.Post,
        )
        return response["request_id"]

    def raise_on_error(self, response: Response) -> None:
        """
        Convenience function to quickly check if response
        contains an error value.
        """
        if isinstance(response.body, ErrorResponse):
            raise ErrorResponseException(response.body)

    async def _http_request(
        self,
        url: str,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
        rtype: RequestType = RequestType.Get,
        fail_on_404: bool = True,
    ) -> dict | aiohttp.ClientResponse:
        """
        Utility function to handle HTTP requests more easily
        """
        url = self._url + url
        last_exception = None
        if headers is None:
            headers = {}
        # Add authentication secret if provided
        if self._secret:
            headers["X-DFM-Auth"] = self._secret
        for _ in range(self._retries):
            try:
                if body:
                    logging.info("Calling %s with body: %s", url, body)
                if not body:
                    body = {}
                self._log.debug("Calling %s with body: %s", url, body)
                async with self._session.request(
                    rtype.name,
                    url,
                    json=body,
                    headers=headers,
                    timeout=self._timeout,
                ) as response:
                    self._log.debug("Initial response %s", response)
                    if response.status == 404 and not fail_on_404:
                        return None
                    r = await response.json()
                    self._log.debug("Returning response: %s", r)
                    response.raise_for_status()
                    return r
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_exception = e
                await asyncio.sleep(self._backoff)
        if last_exception:
            raise last_exception

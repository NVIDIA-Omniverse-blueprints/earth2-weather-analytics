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
Implementation of Process service
"""
import json
import logging
import os
from uuid import uuid4
from typing import List, Literal

import redis.asyncio
from redis.commands.json.path import Path

from fastapi import (
    FastAPI,
    HTTPException,
    Request,
    Response as FastApiResponse,
    status as FastApiStatus,
)
from fastapi.concurrency import asynccontextmanager
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

import dfm
from dfm.api import Process, FunctionCall
from dfm.api.response import ProcessResponse, Response
from dfm.api.discovery import BranchFieldAdvice, SingleFieldAdvice
from dfm.common import AdviseableBaseModel
from dfm.service.common.logging import getLogger
from dfm.service.common.auth import get_auth
from dfm.service.common.pubsub import Channel, Service
from dfm.service.common.data import RequestState
from dfm.service.common.message import Job

use_fake_redis = os.environ.get("K8S_PROCESS_USE_FAKE_REDIS", "false") == "true"
if use_fake_redis:
    from fakeredis import FakeServer
    from fakeredis.aioredis import FakeRedis as AsyncFakeRedis

    fake_redis_server = FakeServer()

# fixes recursions, else pydantic raises
# 'MockValSer' object cannot be converted to 'SchemaSerializer'
# if the first input to the model is a dictionnary
BranchFieldAdvice.model_rebuild(force=True)
SingleFieldAdvice.model_rebuild(force=True)

FunctionCall.set_allow_outside_block()


class AuthMiddleware(BaseHTTPMiddleware):  # pylint: disable=too-few-public-methods
    """
    Add middleware to validate the API key
    """

    async def dispatch(self, request: Request, call_next):
        # Authenticate request
        api_key = request.headers.get("X-DFM-Auth")
        if not app.state.auth.authenticate(api_key):
            return JSONResponse(
                status_code=403,
                content={"detail": "Request did not provide valid credentials"},
            )
        # If the authentication succeeded, proceed with the request
        response = await call_next(request)
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """FastAPI lifespan management"""

    logging.getLogger().setLevel(logging.INFO)
    logging.info("Process service starting up.")

    # Set version information
    _app.version = dfm.__version__
    logging.info("Process service version: %s", _app.version)

    _app.state.site_name = os.environ.get("K8S_PROCESS_SITE_NAME")
    if not _app.state.site_name:
        raise ValueError("Please set site name in K8S_PROCESS_SITE_NAME env var")

    # Connect to Redis instance
    redis_host = os.environ.get("K8S_PROCESS_REDIS_HOST", "redis")
    redis_port = int(os.environ.get("K8S_PROCESS_REDIS_PORT", "6379"))
    redis_db = os.environ.get("K8S_PROCESS_REDIS_DB", "0")
    redis_password = os.environ.get("K8S_PROCESS_REDIS_PASSWORD", None)
    logging.info(
        "Connecting to %sRedis %s:%s db=%s %s",
        "fake " if use_fake_redis else "",
        redis_host,
        redis_port,
        redis_db,
        "with password" if redis_password else "",
    )

    if use_fake_redis:
        # Use FakeRedis for testing. Patching our way through is
        # problematic with FastAPI and whatnot, so it's just 10x
        # easier to explicitly use fake.
        _app.state.redis = AsyncFakeRedis(
            decode_responses=True, server=fake_redis_server
        )
    else:
        _app.state.redis = redis.asyncio.Redis(  # pragma: no cover
            host=redis_host,
            port=redis_port,
            db=redis_db,
            password=redis_password,
            decode_responses=True,
        )
    _app.state.consumer_id = str(uuid4())
    _app.state.execute_channel = await Channel(
        Service.ANY, Service.EXECUTE, "req", Job, _app.state.redis
    )
    _app.state.scheduler_channel = await Channel(
        Service.ANY, Service.SCHEDULER, "req", Job, _app.state.redis
    )
    yield
    logging.info("Process service shutting down.")


log = getLogger(__name__)

app = FastAPI(lifespan=lifespan, title="DFM Process")

# Set up authentication middleware
app.state.auth = get_auth(log)
app.add_middleware(AuthMiddleware)


@app.get("/status")
async def status():
    """
    Get health status of the application.

    Currently the service is always happy and returns OK when asked for status.

    Returns:
    - **200 OK**: Service healthy
    """

    resp = {"status": "OK"}
    log.info("Returning %s", json.dumps(resp, indent=4))
    return resp


@app.get("/version")
async def version():
    """
    Returns service version.
    """
    resp = {"version": app.version, "name": app.title}
    log.info("Returning %s", json.dumps(resp, indent=4))
    return resp


@app.post("/process")
async def process(
    request: Request, mode: Literal["execute", "discovery"] = "execute"
) -> ProcessResponse:
    """
    Create process request

    Returns:
    - **200 OK**: Execution result (json)
    - **500 Internal Server Error **: Not sure yet
    """
    request_id = uuid4()
    logger = getLogger(__name__, request_id)

    # validate request here and parse it into a Process struct
    # depends on the mode being discovery or not
    is_discovery = mode == "discovery"
    json_param = await request.body()
    try:
        logger.info(
            f"trying to validate json input: {json_param}, mode is set to {mode}"
        )
        old_value = AdviseableBaseModel.set_allow_advise(is_discovery)
        request = Process.model_validate_json(json_param)
        AdviseableBaseModel.set_allow_advise(old_value)
        logger.info(f"decoded request: {request}")
    except ValidationError as e:
        logger.exception("caught exception")
        raise RequestValidationError(e.errors()) from e

    logger.info(
        "Assigned request id %s to request: %s", request_id, request.model_dump_json()
    )

    if request.deadline and not request.deadline.tzinfo:
        logger.error(
            "Request %s deadline does not contain time zone information", request_id
        )
        raise HTTPException(422, detail="Deadline requires time zone information")

    # Store request state in the database to allow
    # collecting responses, state tracking, etc.
    state = RequestState(request_id=str(request_id), body=request)
    # assert isinstance(app.state.redis, redis.asyncio.Redis)
    rj = app.state.redis.json()
    await rj.set(
        f"request:{request_id}", Path.root_path(), json.loads(state.model_dump_json())
    )
    logger.info("Stored request status in database with id %s", request_id)

    # Now let the Execute/Scheduler services know that there's job to do
    job = Job(
        home_site=app.state.site_name,
        request_id=request_id,
        deadline=request.deadline,
        execute=request.execute,
        is_discovery=is_discovery,
    )
    channel = (
        app.state.scheduler_channel if request.deadline else app.state.execute_channel
    )
    await channel.publish(job)
    assert isinstance(app.state.execute_channel, Channel)
    logger.info("Published job %s to pubsub channel %s", str(job), channel.name)

    response = ProcessResponse(request_id=request_id)
    logger.info("Returning response: %s", response.model_dump_json())
    return response


@app.get("/request/responses/{request_id}", status_code=200)
async def get_responses(
    request_id: str, response: FastApiResponse, index: int = 0, size: int = 0
) -> List[Response] | None:
    """
    Returns responses for particular request_id. Supports pagination
    in index/size manner.
    """
    logger = getLogger(__name__, request_id)
    # Check if the request is known to us at all
    exists = await app.state.redis.exists(f"request:{request_id}")
    if not exists:
        logger.info("Request %s not found", request_id)
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
    try:
        # Construct path first - start with index
        path = f"$.responses[{index}:"
        if size > 0:
            # ... and add size if provided
            path += str(index + size)
        path += "]"
        assert isinstance(app.state.redis, redis.asyncio.Redis)
        values = await app.state.redis.json().get(f"request:{request_id}", Path(path))
        if values:  # pylint: disable=no-else-return
            responses = []
            for r in values:
                assert isinstance(r, dict)
                responses.append(Response.model_validate(r))
            log.info("Returning %d response(s) ", len(responses))
            log.debug("Returning responses: %s", responses)
            return responses
        else:
            logger.debug("No responses found for request %s", request_id)
            response.status_code = FastApiStatus.HTTP_204_NO_CONTENT
            return None
    except Exception as e:
        logger.error(
            "Data fetching and conversion process raised exception: %s", str(e)
        )
        raise HTTPException(status_code=500, detail=str(e)) from e

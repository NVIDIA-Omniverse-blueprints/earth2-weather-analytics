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
Representation of a user request being handled by the DFM
"""

import datetime
from datetime import timezone
import json
from typing import Dict, Optional
import uuid
from pydantic import UUID4, JsonValue
import redis.asyncio
from dfm.api import FunctionCall
from dfm.api.dfm import PushResponse, Execute, Constant, ReceiveMessage
from dfm.api.response import (
    Response,
    ResponseBody,
    ValueResponse,
    StatusResponse,
    HeartbeatResponse,
    ErrorResponse,
)
from dfm.service.common.exceptions import DfmError, ServerError
from dfm.service.common.message import Package, Job


class DfmRequest:
    def __init__(
        self,
        # only used if there's no "this_site" key in redis (yet), which Uplink sets
        this_site: str,
        home_site: str,
        request_id: UUID4,
        redis_client: redis.asyncio.Redis,
    ):
        self._this_site = this_site
        self._home_site = home_site
        self._request_id = request_id

        self._redis = redis_client

    def __eq__(self, other):
        """
        Returns True if objects has identical data.
        Useful for testing.
        """
        if isinstance(other, DfmRequest):
            eq1 = self._this_site == other._this_site
            eq2 = self._home_site == other._home_site
            eq3 = self._request_id == other._request_id
            _eq4 = self._redis == other._redis
            return eq1 and eq2 and eq3
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    async def _init_async(self):
        # get the name of the site from redis. If Uplink hasn't started and didn't set this
        # field yet, it will be None, which implies that we can only handle local Jobs until
        # uplink has connected
        this_site = await self._redis.get("this_site")
        if this_site:
            # otherwise, keep using the site name given in the constructor
            self._this_site = this_site

        # import here to avoid cirular import. Channel imports logger imports DfmRequest
        from ..pubsub import Channel, Service  # pylint: disable=import-outside-toplevel

        self._execute_channel = (
            await Channel(  # pylint: disable=attribute-defined-outside-init
                Service.ANY, Service.EXECUTE, "req", Job, self._redis
            )
        )
        self._scheduler_channel = (
            await Channel(  # pylint: disable=attribute-defined-outside-init
                Service.ANY, Service.SCHEDULER, "req", Job, self._redis
            )
        )
        self._uplink_channel = (
            await Channel(  # pylint: disable=attribute-defined-outside-init
                Service.ANY, Service.UPLINK, "req", Package, self._redis
            )
        )
        return self

    def __await__(self):
        """
        Allows await DfmRequest()
        """
        return self._init_async().__await__()

    @property
    def this_site(self) -> str:
        return self._this_site

    @property
    def home_site(self) -> str:
        return self._home_site

    @property
    def request_id(self) -> UUID4:
        return self._request_id

    async def push_local_response(self, response: Response):
        rj = self._redis.json()
        # Avoiding problems with UUID serialization in our pydantic models
        magic = json.loads(response.model_dump_json())
        await rj.arrappend(
            f"request:{self._request_id}", ".responses", magic
        )  # type: ignore

    async def schedule_execute(
        self, execute: Execute, deadline: Optional[datetime.datetime] = None
    ):
        job = Job(
            home_site=self.home_site,
            request_id=self.request_id,
            deadline=deadline,
            execute=execute,
        )

        # delay = deadline is not None and deadline > datetime.datetime.now(timezone.utc)
        remote = execute.site and execute.site != self.this_site
        if remote:
            assert execute.site
            # send remotely
            package = Package(
                source_site=self.this_site, target_site=execute.site, job=job
            )
            await self._uplink_channel.publish(package)
        elif job.is_delayed():
            await self._scheduler_channel.publish(job)
        else:
            await self._execute_channel.publish(job)

    async def schedule_node(
        self,
        target_site: Optional[str],
        inputs: Dict[str, JsonValue],
        node: FunctionCall,
        deadline: Optional[datetime.datetime] = None,
    ):
        before = FunctionCall.set_allow_outside_block()
        # for each input, add a constant node with the correct node_id
        body: Dict[UUID4, FunctionCall] = {}
        for input_name, input_val in inputs.items():
            input_uuid: UUID4 = getattr(node, input_name)
            body[input_uuid] = Constant(node_id=input_uuid, value=input_val)
        # and add the node itself that should be executed
        body[node.node_id] = node
        # finally, package it all into an execute script
        execute = Execute(site=target_site, body=body)
        FunctionCall.set_allow_outside_block(before)
        await self.schedule_execute(execute, deadline=deadline)

    async def schedule_body(
        self,
        target_site: Optional[str],
        node_id: Optional[UUID4],  # use this node_id for the execute node
        body: Dict[UUID4, FunctionCall],
        deadline: Optional[datetime.datetime] = None,
    ):
        before = FunctionCall.set_allow_outside_block()
        execute = Execute(
            node_id=node_id if node_id else uuid.uuid4(), site=target_site, body=body
        )
        FunctionCall.set_allow_outside_block(before)
        await self.schedule_execute(execute=execute, deadline=deadline)

    async def send_response(
        self,
        node_id: Optional[UUID4],
        body: ResponseBody,
        deadline: Optional[datetime.datetime] = None,
    ):
        response = Response(node_id=node_id, body=body)

        delay = deadline is not None and deadline > datetime.datetime.now(timezone.utc)
        remote = self.this_site != self.home_site
        if delay or remote:
            # execute delayed and/or remotely; assemble a script to send
            before = FunctionCall.set_allow_outside_block()
            push = PushResponse(
                # use the node_id in the generated node,
                # so the user can match up status responses
                node_id=node_id if node_id else uuid.uuid4(),
                response=response,
            )
            execute = Execute(site=self.home_site, body={push.node_id: push})
            FunctionCall.set_allow_outside_block(before)

            await self.schedule_execute(execute=execute, deadline=deadline)
        else:
            await self.push_local_response(response)

    async def send_value(
        self, node_id: Optional[UUID4], value: JsonValue
    ) -> ValueResponse:
        body = ValueResponse(value=value)
        await self.send_response(node_id, body)
        return body

    async def send_status(
        self, node_id: Optional[UUID4], message: str
    ) -> StatusResponse:
        body = StatusResponse(originating_site=self.this_site, message=message)
        await self.send_response(node_id, body)
        return body

    async def send_heartbeat(self) -> HeartbeatResponse:
        body = HeartbeatResponse(originating_site=self.this_site)
        await self.send_response(None, body)
        return body

    async def send_error(
        self, node_id: Optional[UUID4], error: Exception | DfmError
    ) -> ErrorResponse:
        if not isinstance(error, DfmError):
            body = ServerError.error_response_from_exception(error)
        else:
            body = error.as_error_response()
        await self.send_response(node_id, body)
        return body

    def _mailbox_key(self, mailbox: str):
        return f"{self._request_id}.{mailbox}"

    async def send_message(
        self,
        node_id: Optional[UUID4],
        target_site: Optional[str],
        mailbox: str,
        message: str,
    ):
        remote = target_site and target_site != self.this_site
        if remote:
            assert target_site
            before = FunctionCall.set_allow_outside_block()
            push = ReceiveMessage(
                # use the node_id in the generated node,
                # so the user can match up status responses
                node_id=node_id if node_id else uuid.uuid4(),
                target_site=target_site,
                mailbox=mailbox,
                message=message,
            )
            execute = Execute(site=target_site, body={push.node_id: push})
            FunctionCall.set_allow_outside_block(before)

            await self.schedule_execute(execute=execute, deadline=None)
        else:
            await self._redis.set(self._mailbox_key(mailbox), message)

    async def get_message(self, mailbox: str) -> Optional[str]:
        return await self._redis.get(self._mailbox_key(mailbox))

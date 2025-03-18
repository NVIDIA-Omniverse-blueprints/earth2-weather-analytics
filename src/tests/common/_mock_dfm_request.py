# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import datetime
from typing import List, Optional, Tuple
import uuid
from pydantic import UUID4, JsonValue
from dfm.api.dfm import Execute
from dfm.api.response import Response, ResponseBody
from dfm.service.common.exceptions import DfmError
from dfm.service.common.request import DfmRequest
from dfm.service.common.message import Package, Job


class MockDfmRequest(DfmRequest):
    def __init__(
        self,
        this_site,
        home_site="home",
        collect_errors=False,
        collect_status=False,
        collect_heartbeat=False,
        redis_client=None,
    ):
        super().__init__(
            this_site=this_site,
            home_site=home_site,
            request_id=uuid.uuid4(),
            redis_client=redis_client,  # type: ignore
        )

        self.responses: List[Tuple[Response, Optional[datetime.datetime]]] = []
        self.scheduler_stream: List[Job] = []
        self.execute_stream: List[Job] = []
        self.uplink_stream: List[Package] = []

        self._collect_errors = collect_errors
        self._collect_status = collect_status
        self._collect_heartbeat = collect_heartbeat

    async def _init_async(self):
        raise ValueError("MockDfmRequest isn't meant to be initialized async")

    async def send_response(
        self,
        node_id: UUID4 | None,
        body: ResponseBody,
        deadline: datetime.datetime | None = None,
    ):
        self.responses.append((Response(node_id=node_id, body=body), deadline))

    async def send_value(self, node_id: UUID4 | None, value: JsonValue):
        return await super().send_value(node_id, value)

    async def send_error(self, node_id: UUID4 | None, error: Exception | DfmError):
        if self._collect_errors:
            return await super().send_error(node_id, error)

    async def send_status(self, node_id: UUID4 | None, message: str):
        if self._collect_status:
            return await super().send_status(node_id, message)

    async def send_heartbeat(self):
        if self._collect_heartbeat:
            return await super().send_heartbeat()

    async def push_local_response(self, response: Response):
        self.responses.append((response, None))

    async def schedule_execute(
        self, execute: Execute, deadline: Optional[datetime.datetime] = None
    ):
        job = Job(
            home_site=self.home_site,
            request_id=self.request_id,
            deadline=deadline,
            execute=execute,
        )

        remote = execute.site and execute.site != self.this_site

        if remote:
            assert execute.site
            # send remotely
            package = Package(
                source_site=self.this_site, target_site=execute.site, job=job
            )
            self.uplink_stream.append(package)
        elif job.is_delayed():
            self.scheduler_stream.append(job)
        else:
            self.execute_stream.append(job)

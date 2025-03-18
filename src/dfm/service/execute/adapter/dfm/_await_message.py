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
from typing import Any
from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.dfm import AwaitMessage as AwaitMessageParams
from dfm.api.dfm import Constant
from dfm.api import FunctionCall
from dfm.service.common.exceptions import ServerError


class AwaitMessage(NullaryAdapter[Provider, None, AwaitMessageParams]):
    """
    A AwaitMessage adapter is an adapter that awaits a message from a mailbox.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: AwaitMessageParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def body(self) -> Any:
        async def async_body():
            message = await self._dfm_request.get_message(self.params.mailbox)
            if message:
                self._logger.info("Awaited message has arrived: %s", message)
                # Nodes inside the await body are referencing the await node to get
                # the result. Now that we have the message, take the await body and
                # add a constant with the same id as the await node (e.g if
                # with AwaitMessage as xyz:
                #   Foo(data=xyz)
                # We "pass the message into the body" by constructing a new body:
                # xyz = Constant(message)
                # Foo(data=xyz)
                body = self.params.body
                before = FunctionCall.set_allow_outside_block()
                body[self.params.node_id] = Constant(
                    node_id=self.params.node_id, value=message
                )
                FunctionCall.set_allow_outside_block(before)
                await self._dfm_request.schedule_body(
                    target_site=None,
                    node_id=self.params.node_id,
                    body=body,
                    deadline=None,
                )
                return None
            elif self.params.wait_count < 500:
                self._logger.info(
                    "Awaited message still not here. Re-scheduling myself"
                )
                # reschedule ourselves until message arrives
                deadline = datetime.datetime.now(datetime.UTC) + datetime.timedelta(
                    seconds=self.params.sleeptime
                )

                new_params = self.params.model_copy(
                    update={"wait_count": self.params.wait_count + 1}
                )
                await self._dfm_request.schedule_node(
                    target_site=None, inputs={}, node=new_params, deadline=deadline
                )
                return None
            else:
                self._logger.error(
                    "AwaitMessage was re-scheduled too many times. Giving up"
                )
                await self._dfm_request.send_error(
                    node_id=self.params.node_id,
                    error=ServerError(
                        "AwaitMessage was re-scheduled too many times. Giving up"
                    ),
                )
                return None

        return async_body()

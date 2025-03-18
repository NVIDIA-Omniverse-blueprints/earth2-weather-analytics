# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any
from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import UnaryAdapter, Adapter
from dfm.api.dfm import SendMessage as SendMessageParams


class SendMessage(UnaryAdapter[Provider, None, SendMessageParams], input_name="data"):
    """
    A SendMessage adapter is an adapter that sends a message to a node.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: SendMessageParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data) -> Any:
        async def async_body():
            await self.dfm_request.send_message(
                node_id=self.params.node_id,
                target_site=self.params.target_site,
                mailbox=self.params.mailbox,
                message=str(data),
            )
            self._logger.info(
                "Sent message %s to %s@%s",
                str(data),
                self.params.mailbox,
                self.params.target_site,
            )
            return None

        return async_body()

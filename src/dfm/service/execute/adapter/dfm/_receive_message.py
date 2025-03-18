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
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.dfm import ReceiveMessage as ReceiveMessageParams


class ReceiveMessage(NullaryAdapter[Provider, None, ReceiveMessageParams]):
    """
    A ReceiveMessage adapter is an adapter that receives a message from a node.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ReceiveMessageParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def body(self) -> Any:
        async def async_body():
            # Most likely, some other site assembled and sent a ReceiveMessage() script.
            # And presumably, the ReceiveMessage param's target site is here, otherwise
            # it would have been routed somewhere else. But even if not, doesn't matter,
            # because dfm_request would simply forward the message to the target site
            await self.dfm_request.send_message(
                node_id=self.params.node_id,
                target_site=self.params.target_site,
                mailbox=self.params.mailbox,
                message=self.params.message,
            )
            return None

        return async_body()

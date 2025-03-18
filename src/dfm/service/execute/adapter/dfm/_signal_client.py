# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, AsyncIterator

from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter
from dfm.api.dfm import SignalClient as SignalClientParams


class SignalClient(Adapter[Provider, None, SignalClientParams]):
    """
    A SignalClient adapter is an adapter that sends a signal to a client.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: SignalClientParams,
        after: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params)
        self._set_input_adapter("after", after)

    async def stream_body(self) -> AsyncIterator[Any]:
        input_adapter = self.get_input_adapter("after")
        input_stream = await input_adapter.get_or_create_stream()
        # read all the items from the input stream
        async for _item in input_stream:
            # Check if input is still healthy
            input_stream.raise_if_exception()
        # input stream is done, yield the message
        yield self.params.message

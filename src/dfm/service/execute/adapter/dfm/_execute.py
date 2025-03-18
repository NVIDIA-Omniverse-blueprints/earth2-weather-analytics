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
from dfm.api.dfm import Execute as ExecuteParams


class Execute(NullaryAdapter[Provider, None, ExecuteParams]):
    """
    A Execute adapter is an adapter that executes a function.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ExecuteParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def body(self) -> Any:
        # this Execute adapter is executed because there's an Execute node
        # in a surrounding body. We are currently executing the surrounding body

        # the DfmRequest implements the routing logic
        async def async_body():
            self._logger.info("Scheduling Execute's body")
            await self.dfm_request.schedule_execute(self.params, deadline=None)
            return None

        return async_body()

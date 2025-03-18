# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import textwrap
from typing import Awaitable
from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.dfm import PushResponse as PushResponseParams
from dfm.service.common.logging import getLogger


class PushResponse(NullaryAdapter[Provider, None, PushResponseParams]):
    """
    A PushResponse adapter is an adapter that pushes a response to the local site.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: PushResponseParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def body(self) -> Awaitable:
        response = self.params.response
        logger = getLogger(__name__, self.dfm_request)
        logger.info(
            "Pushing new response for request %s, %s",
            self.dfm_request.request_id,
            textwrap.shorten(str(response), 80),
        )
        return self.dfm_request.push_local_response(response)

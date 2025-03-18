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
from dfm.config.adapter.dfm import GreetMe as GreetMeConfig
from dfm.api.dfm import GreetMe as GreetMeParams


class GreetMe(NullaryAdapter[Provider, GreetMeConfig, GreetMeParams]):
    """
    A GreetMe adapter is the equivalent of a `Hello World` in the DFM.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: GreetMeConfig,
        params: GreetMeParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def body(self) -> Any:
        result = f"{self.config.greeting} {self.params.name}"
        return result

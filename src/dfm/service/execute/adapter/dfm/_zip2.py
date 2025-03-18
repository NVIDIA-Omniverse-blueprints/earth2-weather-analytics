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
from dfm.service.execute.adapter import Adapter, BinaryZipAdapter
from dfm.api.dfm import Zip2 as Zip2Params


class Zip2(
    BinaryZipAdapter[Provider, None, Zip2Params], input1_name="lhs", input2_name="rhs"
):
    """
    A Zip2 adapter is an adapter that zips two adapters together.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        params: Zip2Params,
        lhs: Adapter,
        rhs: Adapter,
    ):
        super().__init__(dfm_request, provider, None, params, lhs, rhs)

    def body(self, lhs, rhs) -> Any:
        return (lhs, rhs)

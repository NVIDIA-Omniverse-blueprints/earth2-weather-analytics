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
from typing import Any
import xarray
from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, BinaryZipAdapter
from dfm.api.xarray import AveragePointwise as AveragePointwiseParams


class AveragePointwise(
    BinaryZipAdapter[Provider, None, AveragePointwiseParams],
    input1_name="lhs",
    input2_name="rhs",
):
    """
    An AveragePointwise adapter is an adapter that averages two datasets pointwise.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: AveragePointwiseParams,
        lhs: Adapter,
        rhs: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, lhs, rhs)

    def body(self, lhs: xarray.Dataset, rhs: xarray.Dataset) -> Any:
        self._logger.info(
            "average pointwise of %s and %s",
            textwrap.shorten(str(lhs), width=80),
            textwrap.shorten(str(rhs), width=80),
        )
        lhs = lhs.fillna(0)
        rhs = rhs.fillna(0)
        if "lat" in rhs.variables:
            rhs = rhs.rename({"lat": "latitude"})
        if "lon" in rhs.variables:
            rhs = rhs.rename({"lon": "longitude"})
        if lhs.max().to_array().max().compute().item() < 1.0:
            self._logger.warning("AveragePointwise is fudging lhs")
            lhs = rhs
        elif rhs.max().to_array().max().compute().item() < 1.0:
            self._logger.warning("AveragePointwise is fudging rhs")
            rhs = lhs
        ds = (lhs + rhs) / 2.0
        ds = ds.squeeze()
        return ds.compute()

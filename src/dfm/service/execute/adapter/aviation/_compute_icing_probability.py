# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to compute icing probability from temperature and humidity."""

from typing import Any

import numpy as np
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.aviation import ComputeIcingProbability as ComputeIcingProbabilityParams


# Common variable naming patterns
TEMP_PATTERNS = ["t2m", "t850", "t700", "t500", "t_{}", "tmp{}"]
RH_PATTERNS = ["r2m", "r850", "r700", "r500", "r_{}", "rh{}", "rhprs{}"]


def _find_temp_rh_vars(data: xarray.Dataset):
    """Find temperature and relative humidity variables."""
    data_vars = list(data.data_vars)
    temp_vars = [v for v in data_vars if v.startswith(("t", "tmp")) and any(c.isdigit() for c in v)]
    rh_vars = [v for v in data_vars if v.startswith(("r", "rh")) and any(c.isdigit() for c in v)]

    # Also check for t2m and r2m
    if "t2m" in data_vars:
        temp_vars.append("t2m")
    if "r2m" in data_vars:
        rh_vars.append("r2m")

    return temp_vars, rh_vars


class ComputeIcingProbability(
    UnaryAdapter[Provider, None, ComputeIcingProbabilityParams], input_name="data"
):
    """Adapter to compute icing probability from temperature and humidity fields.

    Uses a threshold model where icing probability is proportional to
    relative humidity above a threshold, gated by temperature being in
    the supercooled water range.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ComputeIcingProbabilityParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        temp_vars, rh_vars = _find_temp_rh_vars(data)

        if not temp_vars:
            raise DataError(
                f"No temperature variables found. Available: {list(data.data_vars)}"
            )
        if not rh_vars:
            raise DataError(
                f"No relative humidity variables found. Available: {list(data.data_vars)}"
            )

        # Use first available temp and RH (prefer pressure level vars over surface)
        temp_name = temp_vars[0]
        rh_name = rh_vars[0]

        temp = data[temp_name]
        rh = data[rh_name]

        # Convert temperature to Celsius if in Kelvin (ERA5 uses Kelvin)
        temp_c = xarray.where(temp > 100, temp - 273.15, temp)

        # Icing probability model
        # 1. Temperature must be in supercooled range
        temp_mask = (temp_c >= self.params.temp_range_min) & (
            temp_c <= self.params.temp_range_max
        )

        # 2. Humidity contribution: linear scale from rh_threshold to 100%
        rh_factor = (rh - self.params.rh_threshold) / (100.0 - self.params.rh_threshold)
        rh_factor = rh_factor.clip(min=0, max=1)

        # 3. Temperature weighting: peak probability near -10C
        temp_weight = 1.0 - abs(temp_c - (-10.0)) / max(
            abs(self.params.temp_range_max - (-10.0)),
            abs(self.params.temp_range_min - (-10.0)),
        )
        temp_weight = temp_weight.clip(min=0.2, max=1.0)

        # Combined probability
        icing_prob = xarray.where(temp_mask, rh_factor * temp_weight, 0.0)
        icing_prob = icing_prob.clip(min=0, max=1)
        icing_prob.name = self.params.output_name

        output_ds = icing_prob.to_dataset()
        output_ds[self.params.output_name].attrs.update(
            {
                "description": "Icing probability (0=none, 1=certain)",
                "units": "",
                "temp_var_used": temp_name,
                "rh_var_used": rh_name,
                "temp_range_c": [self.params.temp_range_min, self.params.temp_range_max],
                "rh_threshold": self.params.rh_threshold,
                "data_min": float(icing_prob.min().data),
                "data_max": float(icing_prob.max().data),
            }
        )
        return output_ds

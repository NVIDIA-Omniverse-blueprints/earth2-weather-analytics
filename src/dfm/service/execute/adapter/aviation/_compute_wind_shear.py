# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to compute vertical wind shear from u/v wind at pressure levels."""

from typing import Any

import numpy as np
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.aviation import ComputeWindShear as ComputeWindShearParams


# Standard pressure levels in hPa (descending = ascending altitude)
STANDARD_LEVELS = [1000, 925, 850, 700, 500, 400, 300, 250, 200, 150, 100, 50]


def _find_wind_variables(data: xarray.Dataset):
    """Find u/v wind variable pairs at pressure levels in the dataset.

    Looks for naming patterns like u850/v850, u_850/v_850, etc.
    Returns dict mapping pressure_level -> (u_var_name, v_var_name).
    """
    pairs = {}
    data_vars = list(data.data_vars)
    for level in STANDARD_LEVELS:
        u_candidates = [f"u{level}", f"u_{level}", f"ugrd{level}"]
        v_candidates = [f"v{level}", f"v_{level}", f"vgrd{level}"]
        u_name = next((c for c in u_candidates if c in data_vars), None)
        v_name = next((c for c in v_candidates if c in data_vars), None)
        if u_name and v_name:
            pairs[level] = (u_name, v_name)
    return pairs


class ComputeWindShear(
    UnaryAdapter[Provider, None, ComputeWindShearParams], input_name="data"
):
    """Adapter to compute vertical wind shear between pressure levels."""

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ComputeWindShearParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        """Compute vertical wind shear magnitude between pressure levels.

        Wind shear = sqrt((du/dp)^2 + (dv/dp)^2) where dp is the
        pressure difference between levels.
        """
        wind_vars = _find_wind_variables(data)
        if len(wind_vars) < 2:
            raise DataError(
                f"Need at least 2 pressure levels with u/v winds, found {len(wind_vars)}. "
                f"Available variables: {list(data.data_vars)}"
            )

        # Determine level pairs
        sorted_levels = sorted(wind_vars.keys(), reverse=True)  # descending pressure = ascending alt
        if self.params.level_pairs:
            level_pairs = self.params.level_pairs
        else:
            level_pairs = list(zip(sorted_levels[:-1], sorted_levels[1:]))

        shear_arrays = []
        shear_level_labels = []

        for lower_p, upper_p in level_pairs:
            if lower_p not in wind_vars or upper_p not in wind_vars:
                continue

            u_lower_name, v_lower_name = wind_vars[lower_p]
            u_upper_name, v_upper_name = wind_vars[upper_p]

            du = data[u_upper_name] - data[u_lower_name]
            dv = data[v_upper_name] - data[v_lower_name]
            dp = float(lower_p - upper_p) * 100.0  # hPa to Pa

            shear = np.sqrt(du**2 + dv**2) / dp
            shear_arrays.append(shear)
            shear_level_labels.append(f"{lower_p}-{upper_p}")

        if not shear_arrays:
            raise DataError("No valid level pairs found for wind shear computation")

        # Average shear across all level pairs for a single output field
        stacked = xarray.concat(shear_arrays, dim="level_pair")
        mean_shear = stacked.mean(dim="level_pair")
        mean_shear.name = self.params.output_name

        output_ds = mean_shear.to_dataset()
        output_ds[self.params.output_name].attrs.update(
            {
                "description": "Vertical wind shear magnitude",
                "units": "1/s",
                "level_pairs": shear_level_labels,
                "data_min": float(mean_shear.min().data),
                "data_max": float(mean_shear.max().data),
            }
        )
        return output_ds

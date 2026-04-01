# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to score flight route segments for aviation hazards."""

from typing import Any

import numpy as np
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.aviation import ScoreRouteHazards as ScoreRouteHazardsParams


DEFAULT_WEIGHTS = {
    "turbulence": 0.4,
    "icing": 0.3,
    "wind_shear": 0.3,
}

# Mapping from hazard name to variable patterns in the route weather dataset
HAZARD_VAR_PATTERNS = {
    "turbulence": ["ellrod_ti", "turbulence", "tke"],
    "icing": ["icing_prob", "icing"],
    "wind_shear": ["wind_shear", "shear"],
}


def _normalize_0_1(arr):
    """Normalize array to 0-1 range."""
    arr_min = np.nanmin(arr)
    arr_max = np.nanmax(arr)
    if arr_max - arr_min < 1e-10:
        return np.zeros_like(arr)
    return (arr - arr_min) / (arr_max - arr_min)


class ScoreRouteHazards(
    UnaryAdapter[Provider, None, ScoreRouteHazardsParams], input_name="data"
):
    """Adapter to compute weighted hazard scores along a flight route.

    Takes route weather data (from ExtractRouteWeather) and computes
    a composite hazard score per route segment.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ScoreRouteHazardsParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        weights = self.params.weights or DEFAULT_WEIGHTS

        # Normalize weights to sum to 1
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}

        n_points = len(data.route_point) if "route_point" in data.dims else len(data.coords.get("route_point", []))
        hazard_score = np.zeros(n_points)
        active_hazards = {}

        for hazard_name, weight in weights.items():
            patterns = HAZARD_VAR_PATTERNS.get(hazard_name, [hazard_name])
            var_name = None
            for pattern in patterns:
                if pattern in data.data_vars:
                    var_name = pattern
                    break

            if var_name is None:
                continue

            values = data[var_name].values.astype(float)
            normalized = _normalize_0_1(values)
            hazard_score += weight * normalized
            active_hazards[hazard_name] = var_name

        # Clip to 0-1
        hazard_score = np.clip(hazard_score, 0, 1)

        # Add hazard score to dataset
        output_ds = data.copy()
        output_ds[self.params.output_name] = ("route_point", hazard_score)
        output_ds[self.params.output_name].attrs.update(
            {
                "description": "Composite aviation hazard score (0=safe, 1=severe)",
                "weights": weights,
                "active_hazards": active_hazards,
                "mean_score": float(np.nanmean(hazard_score)),
                "max_score": float(np.nanmax(hazard_score)),
                "segments_above_0.5": int(np.sum(hazard_score > 0.5)),
                "segments_above_0.8": int(np.sum(hazard_score > 0.8)),
            }
        )

        return output_ds

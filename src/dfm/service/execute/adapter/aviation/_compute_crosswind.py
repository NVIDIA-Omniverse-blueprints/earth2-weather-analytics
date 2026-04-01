# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to compute crosswind and headwind components for a runway."""

from typing import Any

import numpy as np
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.aviation import ComputeCrosswind as ComputeCrosswindParams


class ComputeCrosswind(
    UnaryAdapter[Provider, None, ComputeCrosswindParams], input_name="data"
):
    """Adapter to decompose surface winds into crosswind/headwind components.

    Extracts wind at the nearest grid point to the airport and decomposes
    into crosswind (perpendicular to runway) and headwind (along runway)
    components.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ComputeCrosswindParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        # Find surface wind variables
        u_var = v_var = None
        for u_candidate, v_candidate in [
            ("u10m", "v10m"),
            ("u10", "v10"),
            ("u_10m", "v_10m"),
        ]:
            if u_candidate in data.data_vars and v_candidate in data.data_vars:
                u_var, v_var = u_candidate, v_candidate
                break

        if not u_var:
            raise DataError(
                f"Cannot find surface wind (u10m/v10m). Available: {list(data.data_vars)}"
            )

        # Determine coordinate names
        lat_coord = "latitude" if "latitude" in data.coords else "lat"
        lon_coord = "longitude" if "longitude" in data.coords else "lon"

        # Extract wind at nearest grid point to airport
        u_wind = data[u_var].sel(
            {lat_coord: self.params.airport_lat, lon_coord: self.params.airport_lon},
            method="nearest",
        )
        v_wind = data[v_var].sel(
            {lat_coord: self.params.airport_lat, lon_coord: self.params.airport_lon},
            method="nearest",
        )

        # Compute meteorological wind direction (direction wind is FROM)
        wind_speed = np.sqrt(u_wind**2 + v_wind**2)
        wind_dir_rad = np.arctan2(-u_wind, -v_wind)
        wind_dir_deg = np.rad2deg(wind_dir_rad) % 360

        # Convert to knots (m/s * 1.94384)
        wind_speed_kts = wind_speed * 1.94384

        # Runway heading to radians
        rwy_rad = np.deg2rad(self.params.runway_heading)
        wind_rad = np.deg2rad(wind_dir_deg)

        # Angle between wind and runway
        angle_diff = wind_rad - rwy_rad

        # Headwind component (positive = headwind, negative = tailwind)
        headwind = wind_speed_kts * np.cos(angle_diff)
        # Crosswind component (absolute value, positive = from right)
        crosswind = wind_speed_kts * np.sin(angle_diff)

        headwind.name = f"{self.params.output_name}_head"
        crosswind.name = f"{self.params.output_name}_cross"

        output_ds = xarray.merge([crosswind.to_dataset(), headwind.to_dataset()])
        output_ds.attrs.update(
            {
                "description": f"Crosswind/headwind for runway {self.params.runway_heading:03.0f}",
                "airport_lat": self.params.airport_lat,
                "airport_lon": self.params.airport_lon,
                "runway_heading": self.params.runway_heading,
                "units": "kts",
            }
        )
        return output_ds

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to extract weather data along a flight route."""

from typing import Any

import numpy as np
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.aviation import ExtractRouteWeather as ExtractRouteWeatherParams


def _altitude_ft_to_pressure_hpa(altitude_ft: float) -> float:
    """Convert altitude in feet to pressure in hPa using International Standard Atmosphere."""
    altitude_m = altitude_ft * 0.3048
    # ISA formula: P = P0 * (1 - L*h/T0)^(g*M/(R*L))
    # Below 11km (tropopause)
    if altitude_m <= 11000:
        return 1013.25 * (1 - 0.0065 * altitude_m / 288.15) ** 5.2561
    else:
        # Above tropopause (simplified)
        p_11km = 1013.25 * (1 - 0.0065 * 11000 / 288.15) ** 5.2561
        return p_11km * np.exp(-9.80665 * (altitude_m - 11000) / (287.058 * 216.65))


def _haversine_km(lat1, lon1, lat2, lon2):
    """Great circle distance in km."""
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _interpolate_route(waypoints, spacing_km=50.0):
    """Interpolate waypoints along great circle segments.

    Returns arrays of (lat, lon, altitude_ft, cumulative_distance_km).
    """
    lats, lons, alts, dists = [], [], [], []
    cum_dist = 0.0

    for i in range(len(waypoints) - 1):
        wp1 = waypoints[i]
        wp2 = waypoints[i + 1]
        seg_dist = _haversine_km(wp1["lat"], wp1["lon"], wp2["lat"], wp2["lon"])
        n_points = max(2, int(seg_dist / spacing_km) + 1)

        for j in range(n_points):
            frac = j / (n_points - 1) if n_points > 1 else 0
            lat = wp1["lat"] + frac * (wp2["lat"] - wp1["lat"])
            lon = wp1["lon"] + frac * (wp2["lon"] - wp1["lon"])
            alt = wp1["altitude_ft"] + frac * (wp2["altitude_ft"] - wp1["altitude_ft"])
            dist = cum_dist + frac * seg_dist

            # Avoid duplicate points at segment boundaries
            if i > 0 and j == 0:
                continue

            lats.append(lat)
            lons.append(lon)
            alts.append(alt)
            dists.append(dist)

        cum_dist += seg_dist

    return (
        np.array(lats),
        np.array(lons),
        np.array(alts),
        np.array(dists),
    )


class ExtractRouteWeather(
    UnaryAdapter[Provider, None, ExtractRouteWeatherParams], input_name="data"
):
    """Adapter to extract weather variables along a flight route.

    Interpolates gridded weather data at points along the route,
    converting altitudes to pressure levels for proper vertical sampling.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ExtractRouteWeatherParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        waypoints = self.params.waypoints
        if len(waypoints) < 2:
            raise DataError("Route must have at least 2 waypoints")

        # Validate waypoints
        for i, wp in enumerate(waypoints):
            if "lat" not in wp or "lon" not in wp or "altitude_ft" not in wp:
                raise DataError(
                    f"Waypoint {i} must have 'lat', 'lon', and 'altitude_ft'"
                )

        # Interpolate route
        lats, lons, alts, dists = _interpolate_route(waypoints)
        pressures = np.array([_altitude_ft_to_pressure_hpa(a) for a in alts])

        # Compute time along route
        speed_km_h = self.params.ground_speed_kts * 1.852
        times_h = dists / speed_km_h if speed_km_h > 0 else np.zeros_like(dists)

        # Determine coordinate names
        lat_coord = "latitude" if "latitude" in data.coords else "lat"
        lon_coord = "longitude" if "longitude" in data.coords else "lon"

        # Determine which variables to extract
        variables = self.params.variables
        if variables is None:
            variables = list(data.data_vars)

        # Extract data at each route point
        extracted = {}
        for var_name in variables:
            if var_name not in data.data_vars:
                continue
            var_data = data[var_name]
            values = []
            for lat, lon in zip(lats, lons):
                try:
                    val = float(
                        var_data.sel(
                            {lat_coord: lat, lon_coord: lon}, method="nearest"
                        ).values
                    )
                except Exception:
                    val = np.nan
                values.append(val)
            extracted[var_name] = ("route_point", np.array(values))

        # Build output dataset
        output_ds = xarray.Dataset(
            data_vars=extracted,
            coords={
                "route_point": np.arange(len(lats)),
                "route_lat": ("route_point", lats),
                "route_lon": ("route_point", lons),
                "route_altitude_ft": ("route_point", alts),
                "route_pressure_hpa": ("route_point", pressures),
                "route_distance_km": ("route_point", dists),
                "route_time_h": ("route_point", times_h),
            },
        )

        output_ds.attrs.update(
            {
                "description": "Weather extracted along flight route",
                "n_waypoints": len(waypoints),
                "n_route_points": len(lats),
                "total_distance_km": float(dists[-1]) if len(dists) > 0 else 0,
                "departure_time": self.params.departure_time,
                "ground_speed_kts": self.params.ground_speed_kts,
            }
        )

        return output_ds

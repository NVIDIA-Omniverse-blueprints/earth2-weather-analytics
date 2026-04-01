# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Extract weather data along a flight route from gridded forecasts."""

from typing import Dict, List, Literal, Optional
from .. import FunctionCall, FunctionRef


class ExtractRouteWeather(FunctionCall, frozen=True):
    """
    Extract weather variables along a flight route from gridded forecast data.

    Interpolates gridded weather data at waypoints along a great-circle
    flight path, converting altitude to pressure levels using the
    International Standard Atmosphere.

    Args:
        data: FunctionRef for gridded xarray.Dataset with pressure level data
        waypoints: List of waypoint dicts with keys: lat, lon, altitude_ft, name (optional)
        departure_time: ISO format departure time for time interpolation
        ground_speed_kts: Assumed ground speed in knots for time estimation
        variables: List of variable names to extract along the route
        output_name: Name of the output route weather variable
    """

    api_class: Literal["dfm.api.aviation.ExtractRouteWeather"] = (
        "dfm.api.aviation.ExtractRouteWeather"
    )
    data: FunctionRef
    waypoints: List[Dict]
    departure_time: str
    ground_speed_kts: float = 450.0
    variables: Optional[List[str]] = None
    output_name: str = "route_weather"

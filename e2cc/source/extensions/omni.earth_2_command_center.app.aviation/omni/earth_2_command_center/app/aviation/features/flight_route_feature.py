# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import numpy as np
from pxr import Gf
import omni.earth_2_command_center.app.core.features_api as features_api_module


class FlightRouteFeature(features_api_module.Feature):
    """Feature representing a flight route on the globe.

    Rendered as a color-coded curve where color indicates hazard level.
    """

    feature_type: str = "FlightRoute"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._waypoints = []  # list of dicts: {lat, lon, altitude_ft, name}
        self._hazard_scores = []  # per-segment hazard scores 0-1
        self._route_name = ""
        self._color = Gf.Vec3f(0.0, 1.0, 0.0)  # default green
        self._width = 3.0
        self._points = None  # numpy array of [lat, lon, alt] for rendering
        self._projection = "latlonalt"

    @property
    def waypoints(self):
        return self._waypoints

    @waypoints.setter
    def waypoints(self, value):
        self._property_change("waypoints", value)

    @property
    def hazard_scores(self):
        return self._hazard_scores

    @hazard_scores.setter
    def hazard_scores(self, value):
        self._property_change("hazard_scores", value)

    @property
    def route_name(self):
        return self._route_name

    @route_name.setter
    def route_name(self, value):
        self._property_change("route_name", value)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._property_change("color", value)

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._property_change("width", value)

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, value):
        self._property_change("points", value)

    @property
    def projection(self):
        return self._projection

    @property
    def points_per_curve(self):
        if self._points is not None:
            return [len(self._points)]
        return None

    def set_route_from_waypoints(self):
        """Convert waypoints to points array for rendering."""
        if not self._waypoints:
            return
        pts = []
        for wp in self._waypoints:
            # Convert altitude from feet to km for globe rendering
            alt_km = wp["altitude_ft"] * 0.0003048
            pts.append([wp["lat"], wp["lon"], alt_km])
        self.points = np.array(pts)

    @staticmethod
    def hazard_to_color(score: float) -> Gf.Vec3f:
        """Map hazard score (0-1) to color."""
        if score < 0.3:
            return Gf.Vec3f(0.0, 1.0, 0.0)  # green
        elif score < 0.6:
            return Gf.Vec3f(1.0, 1.0, 0.0)  # yellow
        elif score < 0.8:
            return Gf.Vec3f(1.0, 0.5, 0.0)  # orange
        else:
            return Gf.Vec3f(1.0, 0.0, 0.0)  # red

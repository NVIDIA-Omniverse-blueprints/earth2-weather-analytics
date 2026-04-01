# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from pxr import Gf
import omni.earth_2_command_center.app.core.features_api as features_api_module


# Flight category to color mapping
FLIGHT_CATEGORY_COLORS = {
    "VFR": Gf.Vec3f(0.0, 0.8, 0.0),    # green
    "MVFR": Gf.Vec3f(0.0, 0.0, 1.0),   # blue
    "IFR": Gf.Vec3f(1.0, 0.0, 0.0),    # red
    "LIFR": Gf.Vec3f(1.0, 0.0, 1.0),   # magenta
}


class AirportMarkerFeature(features_api_module.Feature):
    """Feature representing an airport/station on the globe with METAR conditions."""

    feature_type: str = "AirportMarker"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._station_id = ""
        self._latitude = 0.0
        self._longitude = 0.0
        self._altitude = 0.0
        self._flight_category = "VFR"
        self._wind_speed = 0.0
        self._wind_dir = 0.0
        self._visibility = 10.0
        self._ceiling = 99999.0
        self._color = Gf.Vec3f(0.0, 0.8, 0.0)
        self._radius = 30.0

    @property
    def station_id(self):
        return self._station_id

    @station_id.setter
    def station_id(self, value):
        self._property_change("station_id", value)

    @property
    def latitude(self):
        return self._latitude

    @latitude.setter
    def latitude(self, value):
        self._property_change("latitude", value)

    @property
    def longitude(self):
        return self._longitude

    @longitude.setter
    def longitude(self, value):
        self._property_change("longitude", value)

    @property
    def altitude(self):
        return self._altitude

    @altitude.setter
    def altitude(self, value):
        self._property_change("altitude", value)

    @property
    def flight_category(self):
        return self._flight_category

    @flight_category.setter
    def flight_category(self, value):
        self._flight_category = value
        self._color = FLIGHT_CATEGORY_COLORS.get(value, Gf.Vec3f(0.5, 0.5, 0.5))
        self._property_change("flight_category", value)

    @property
    def wind_speed(self):
        return self._wind_speed

    @wind_speed.setter
    def wind_speed(self, value):
        self._property_change("wind_speed", value)

    @property
    def wind_dir(self):
        return self._wind_dir

    @wind_dir.setter
    def wind_dir(self, value):
        self._property_change("wind_dir", value)

    @property
    def visibility(self):
        return self._visibility

    @visibility.setter
    def visibility(self, value):
        self._property_change("visibility", value)

    @property
    def ceiling(self):
        return self._ceiling

    @ceiling.setter
    def ceiling(self, value):
        self._property_change("ceiling", value)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._property_change("color", value)

    @property
    def radius(self):
        return self._radius

    @radius.setter
    def radius(self, value):
        self._property_change("radius", value)

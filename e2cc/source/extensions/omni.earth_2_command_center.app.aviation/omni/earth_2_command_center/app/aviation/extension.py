# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb
import omni.ext

from omni.earth_2_command_center.app.globe_view import get_globe_view

from .features.flight_route_feature import FlightRouteFeature
from .features.airport_marker_feature import AirportMarkerFeature
from .delegates.flight_route_delegate import FlightRouteDelegate
from .delegates.airport_marker_delegate import AirportMarkerDelegate


class AviationExtension(omni.ext.IExt):
    """Extension that registers aviation feature types and their visualization delegates."""

    def on_startup(self, ext_id):
        self._ext_id = ext_id
        carb.log_info("Aviation Visualization Extension Start Up")

        globe_view = get_globe_view()
        globe_view.register_feature_type_delegate(FlightRouteFeature, FlightRouteDelegate)
        globe_view.register_feature_type_delegate(AirportMarkerFeature, AirportMarkerDelegate)

    def on_shutdown(self):
        carb.log_info("Aviation Visualization Extension Shutdown")

        globe_view = get_globe_view()
        globe_view.unregister_feature_type_delegate(FlightRouteFeature, FlightRouteDelegate)
        globe_view.unregister_feature_type_delegate(AirportMarkerFeature, AirportMarkerDelegate)

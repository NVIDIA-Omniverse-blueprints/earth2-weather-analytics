# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['CustomFeature']

import carb

from pxr import Gf

import omni.earth_2_command_center.app.core.features_api as features_api_module

class CustomFeature(features_api_module.Feature):
    feature_type:str = "Custom"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._longitude: float = 8.718287958988796
        self._latitude: float  = 47.34802449611842
        self._altitude: float  = 70.0
        self._color: Gf.Vec3f = Gf.Vec3f(1,0,0)

    @property
    def longitude(self)->float:
        return self._longitude

    @longitude.setter
    def longitude(self, longitude: float):
        self._property_change('longitude', longitude)

    @property
    def latitude(self)->float:
        return self._latitude

    @latitude.setter
    def latitude(self, latitude: float):
        self._property_change('latitude', latitude)

    @property
    def altitude(self)->float:
        return self._altitude

    @altitude.setter
    def altitude(self, altitude: float):
        self._property_change('altitude', altitude)

    @property
    def color(self)->Gf.Vec3f:
        return self._color

    @color.setter
    def color(self, color: Gf.Vec3f):
        self._property_change('color', color)


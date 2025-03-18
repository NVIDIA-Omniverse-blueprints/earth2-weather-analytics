# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'Light', 'Sun']

from .feature import *

class Light(Feature):
    feature_type = "Light"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Sun(Light):
    feature_type:str = "Sun"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._diurnal_motion: bool = True
        self._seasonal_motion: bool = True
        # these are only used when motion is disabled
        self._longitude: float = 0.0
        self._latitude: float  = 0.0

    @property
    def diurnal_motion(self)->bool:
        return self._diurnal_motion

    @diurnal_motion.setter
    def diurnal_motion(self, enabled: bool):
        self._property_change('diurnal_motion', enabled)

    @property
    def seasonal_motion(self)->bool:
        return self._seasonal_motion

    @seasonal_motion.setter
    def seasonal_motion(self, enabled: bool):
        self._property_change('seasonal_motion', enabled)

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


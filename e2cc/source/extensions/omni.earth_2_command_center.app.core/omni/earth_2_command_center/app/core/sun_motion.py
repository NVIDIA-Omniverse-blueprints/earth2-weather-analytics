# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['SunMotion']

from . import features_api
import datetime, math, weakref, calendar, enum

class DeclinationMode(enum.Enum):
    SPENCER=enum.auto()
    COOPER=enum.auto()

class SunMotion:
    """
        helper to handle sun feature position
        ref: https://gml.noaa.gov/grad/solcalc/solareqns.PDF

        need to confirm that this works for all time ranges
    """
    DECLINATION_MODE = DeclinationMode.SPENCER

    def __init__(self, sun_feature: features_api.Sun) -> None:
        self._sun_feature_ref = weakref.ref(sun_feature)
        self._dirty: bool = True
        self._last_time = None

    def feature_property_changed(self):
        self._dirty = True

    def time_changed(self, utc_time: datetime.datetime):
        if self._last_time != utc_time:
            if feature := self._sun_feature_ref():
                if feature.diurnal_motion or feature.seasonal_motion:
                    self._dirty = True

    @property
    def dirty(self)->bool:
        return self._dirty

    def update(self, utc_time: datetime.datetime) -> bool:
        return self.force_update(utc_time) if self._dirty else False

    def force_update(self, utc_time: datetime.datetime) -> bool:
        if feature := self._sun_feature_ref():
            if not feature.active: return False
            feature.latitude = feature.latitude if not feature.seasonal_motion else self._get_declination(utc_time)
            feature.longitude = feature.longitude if not feature.diurnal_motion else (self._get_zenith(utc_time) - 180)
            self._last_time = utc_time
            self._dirty = False
            return True
        return False

    def _get_declination(self, utc_time: datetime.datetime)->float:
        return self._get_declination_spencer(utc_time) if SunMotion.DECLINATION_MODE == DeclinationMode.SPENCER \
            else self._get_declination_cooper(utc_time)

    def _get_declination_spencer(self, utc_time: datetime.datetime)-> float:
        """
        Spencer's formula for computing declination:
          J.W.Spencer. "Fourier series representation of the position of the Sun".
          Search 2 (5), 172 (1971).
        """
        from math import sin, cos
        day = (utc_time - datetime.datetime(utc_time.year, 1, 1, tzinfo=utc_time.tzinfo)).days
        # add time as a day fraction
        day += (utc_time.hour  * 60 + utc_time.minute)/ (24 * 60)
        days_in_year = 366 if calendar.isleap(utc_time.year) else 365
        r = 2 * math.pi * (day - 1) / days_in_year
        decl = 0.006918 - 0.399912 * cos(r) + \
               0.070257 * sin(r) - 0.006758 * cos(2 * r) + \
               0.000907 * sin(2 * r) - 0.002697 * cos(3 * r) + \
               0.00148 * sin (3 * r)
        decl_deg = math.degrees(decl)
        # print(f'SPENCER {utc_time.ctime()}={decl_deg}')
        return decl_deg

    def _get_declination_cooper(self, utc_time:datetime.datetime)->float:
        """
        Cooper's formula:
            P.I.Cooper. "The absorption of solar radiation in solar stills".
            Solar Energy 12 (3), 333-346 (1969).
        """
        from math import sin, cos
        day = (utc_time - datetime.datetime(utc_time.year, 1, 1, tzinfo=utc_time.tzinfo)).days
        # add time as a day fraction
        day += (utc_time.hour  * 60 + utc_time.minute)/ (24 * 60)
        days_in_year = 366 if calendar.isleap(utc_time.year) else 365
        decl = 23.45 * sin( 2 * math.pi * (day + 284) / days_in_year)
        # print(f'COOPER {utc_time.ctime()}={decl}')
        return decl


    def _get_zenith(self, utctime: datetime.datetime)->float:
        return 360 - (utctime.hour * 60 + utctime.minute) / (24 * 60) * 360

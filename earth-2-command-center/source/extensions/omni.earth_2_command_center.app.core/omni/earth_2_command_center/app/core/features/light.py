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
        self._follow_camera: bool  = False

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

    @property
    def follow_camera(self)->bool:
        return self._follow_camera

    @follow_camera.setter
    def follow_camera(self, enabled: bool):
        self._property_change('follow_camera', enabled)

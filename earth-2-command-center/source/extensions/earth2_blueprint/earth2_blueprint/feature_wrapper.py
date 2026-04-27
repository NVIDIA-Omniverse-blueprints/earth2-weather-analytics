__all__ = [ 'is_jpeg_path', 'ImageFeatureWrapper', 'TimestampedJPEGSequence' ]

from pathlib import Path
import datetime
from typing import Optional
import uuid

import carb
import hpcvis.dynamictexture as dt

from omni.earth_2_command_center.app.core.timestamped_sequence import GenericTimestampedSequence
from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features as features
import omni.earth_2_command_center.app.core.features_api as features_api

def is_jpeg_path(path):
    return Path(path).suffix.lower() in [
            '.jpg', '.jpeg', '.jpe', '.jif', '.jfif', '.jfi' ]

class TimestampedJPEGSequence(GenericTimestampedSequence):
    def __init__(self):
        super().__init__()
        self._hooks = [] # clear previous hook
        self.register_hook(self._on_update)
        self._tex = []
        self._cur_timestamp = None

    def _on_update(self, cur_utc_time, target_idx, target_element):
        # target_element is a 2-tuple with timestamp and list element
        timestamp, element = target_element

        # early out if it's still the same timestamp to use
        if timestamp == self._cur_timestamp:
            return
        self._cur_timestamp = timestamp

        to_process = element if isinstance(element, list) else [element]
        num_tex = len(to_process)
        self._validate_tex(num_tex)

        for idx,cur_entry in enumerate(to_process):
            # simplest case: element is single image path
            if isinstance(cur_entry, str):
                if not is_jpeg_path(cur_entry):
                    carb.log_error(f'Trying to load a non-jpeg through the jpeg decoder. Only jpegs are supported for image sequences: {cur_entry}')
                else:
                    self._tex[idx].load_from_url(cur_entry)
                return
            # single bytes buffer
            if isinstance(cur_entry, bytes):
                self._tex[idx].load_from_buffer(cur_entry, dt.BufferFormat.JPEG, dt.BufferSource.Host)

    def _validate_tex(self, num_tex):
        dt_interface = dt.acquire_dynamic_texture_interface()
        while len(self._tex) < num_tex:
            #carb.log_warn(f'adding new dynamic texture to accomodate {num_tex} textures')
            tex = dt_interface.create()
            tex.target_url = f'dynamic://seq_{uuid.uuid4()}'
            self._tex.append(tex)

    @property
    def active(self):
        return [t.active for t in self._tex]

    @active.setter
    def active(self, a):
        a = bool(a)
        for t in self._tex:
            t.active = a

    @property
    def tex(self):
        return self._tex

class FeatureWrapper:
    def __init__(self, feature=None, feature_type=features.Feature,
                 name=None, active=None, *args, **kwargs):
        self._features_api = get_state().get_features_api()
        # we create a feature if it hasn't been provided and we check against the
        # expected feature_type
        if feature is not None:
            if not isinstance(feature, features.Feature):
                raise TypeError(f'{feature} is not of subtype of a E2CC Feature Type')
            self._feature = feature
        else:
            if not issubclass(feature_type, features.Feature):
                raise TypeError(f'{feature_type} is not a subtype of a E2CC Feature Type')
            self._feature = self._features_api.create_feature(feature_type)

        if name is not None:
            self._feature.name = name
        if active is not None:
            self._feature.active = bool(active)

        self._feature_subscription = self._features_api.get_event_stream().create_subscription_to_push(self._on_feature_change)

    @property
    def feature(self):
        return self._feature

    @property
    def features_api(self):
        return self._features_api

    @property
    def type(self):
        return type(self._feature)

    def add(self):
        if self.feature is not None:
            self._features_api.add_feature(self.feature)

    def remove(self):
        if self.feature is not None:
            self._features_api.remove_feature(self.feature)

    def _on_feature_change(self, event):
        change = event.payload['change']
        feature_type = event.payload['feature_type']

        if change['id'] == features_api.FeatureChange.FEATURE_CLEAR['id']:
            self._on_feature_clear(event)
        if change['id'] == features_api.FeatureChange.PROPERTY_CHANGE['id']:
            self._on_feature_change(event)
        if change['id'] == features_api.FeatureChange.FEATURE_REMOVE['id']:
            self._on_feature_remove(event)

    def _on_feature_clear(self, event):
        pass

    def _on_feature_change(self, event):
        pass

    def _on_feature_remove(self, event):
        pass

    @property
    def visible(self):
        return self.feature.active

    @visible.setter
    def visible(self, v):
        v = bool(v)
        self.feature.active = v

    def __del__(self):
        self._feature_subscription.unsubscribe()

class ImageFeatureWrapper(FeatureWrapper):
    def __init__(self, colormap=None, *args, **kwargs):
        super().__init__(feature_type=features.Image, *args, **kwargs)
        self._seq = TimestampedJPEGSequence()

        if colormap is not None:
            self._feature.colormap = str(colormap)

    def add_image(self, timestamp, img):
        if not isinstance(timestamp, datetime.datetime):
            carb.log_error(f'add_image called with invalid timestamp type: {type(timestamp)}, expected datetime')
            return
        #carb.log_warn(f'adding image to {self._feature.name} at {timestamp}')
        self._seq.insert(timestamp, img) # no copy needed as bytes type is immutable
        self._feature.alpha_sources = [t.target_url for t in self._seq.tex]

    def clear_images(self):
        self._feature.alpha_sources = []
        self._feature.time_coverage = None
        self._feature.meta = {}
        self._seq.clear()

    @property
    def visible(self):
        return super().visible

    @visible.setter
    def visible(self, v):
        v = bool(v)
        FeatureWrapper.visible.fset(self, v)
        self._seq.active = v

    def _on_feature_clear(self, event):
        super()._on_feature_clear(event)
        self.visible = False

    def _on_feature_change(self, event):
        super()._on_feature_change(event)
        if event.payload['property'] == 'active':
            self.visible = self.feature.active

    def _on_feature_remove(self, event):
        super()._on_feature_remove(event)
        self.visible = False

    def __del__(self):
        carb.log_warn('deleting image feature wrapper')


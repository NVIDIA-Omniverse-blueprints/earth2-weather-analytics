# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'FeaturesAPI',
           'FeatureChange',
           'Feature', 'Image', 'Marker', 'Volume', 'Light', 'Sun']

import carb.events

from datetime import datetime
from typing import Any, List, Callable, Optional, TypeVar

# import all feature types
from .features.feature import *
from .features.image import *
from .features.light import *
from .features.misc import *

import numpy as np

class FeaturesAPI:
    def __init__(self):
        super().__init__()

        self._feature_id_counter = 1
        self._feature_list: List[Feature] = []

        events = carb.events.acquire_events_interface()
        self._feature_list_stream = events.create_event_stream()

    # ========================================
    # Feature Creation
    # ========================================
    T = TypeVar('T')
    def create_feature(self, cls: type[T], *args: Any, **kwargs: Any) -> T:
        return cls(*args, features_api=self, feature_id=self._get_next_feature_id(), **kwargs)

    def create_image_feature(self) -> Image:
        return self.create_feature(Image)

    def create_marker_feature(self) -> Marker:
        return self.create_feature(Marker)

    def create_volume_feature(self) -> Volume:
        return self.create_feature(Volume)

    def create_light_feature(self) -> Light:
        return self.create_feature(Light)

    def create_sun_feature(self) -> Sun:
        return self.create_feature(Sun)

    def create_curves_feature(self) -> Curves:
        return self.create_feature(Curves)

    # ========================================
    # Feature List Management
    # ========================================
    def get_features(self):
        '''Returns a list of all features currently registered'''
        return self._feature_list.copy()

    #def set_feature_list(self, feature_list: List[Feature]):
    #    self._feature_list = feature_list

    def add_feature(self, feature: Feature, pos: Optional[int] = None):
        '''Adds a feature to the feature stack, optionally at a certain position'''
        if pos is not None:
            self._feature_list.insert(pos, feature)
        else:
            self._feature_list.append(feature)
        feature._register_change(FeatureChange.FEATURE_ADD)

    def remove_feature(self, feature: Feature):
        '''Removes a feature from the feature stack'''
        if (feature in self._feature_list):
            self._feature_list.remove(feature)
            feature._register_change(FeatureChange.FEATURE_REMOVE, force_send=True)   # type: ignore

    def clear(self):
        '''Clears the current feature stack'''
        self._feature_list = []
        self.get_event_stream().push(FeatureChange.FEATURE_CLEAR['id'], 0,
                                     payload={'change': FeatureChange.FEATURE_CLEAR})
        self.get_event_stream().pump()

    def reorder_features(self, permutation):
        '''Reorders the feature stack

        If permutation is a list, it's assumed to be a permutation list, so a list
        of the same length of the current feature stack with unique indices indicating
        the new position of each feature.

        If permutation is a dictionary, it's assumed to represent feature->position
        mappings.

        In both cases, the permutation is performed and a reorder event is sent
        that contains the permutation list in its payload.
        '''
        permuted_list = self._feature_list.copy()
        permutation_list = None

        # if it's a list, we assume it's a permutation list
        if isinstance(permutation, list):
            # first check we have the right amount of entries
            if len(permutation) != len(self._feature_list):
                carb.log_error('feature reorder requested with inconsistent number of entries')
                return

            # now make sure there are no duplicates
            if len(set(permutation)) != len(permutation):
                carb.log_error('feature reorder requested with duplicate entries')
                return

            # permute the list
            permuted_list = [permuted_list[i] for i in permutation]
            permutation_list = permutation

        # if it's a dict, we assume it's a repositioning mapping
        elif isinstance(permutation, dict):
            try:
                permutation_list = np.arange(len(self._feature_list)).tolist()
                for feature, new_pos in permutation.items():
                    index = permuted_list.index(feature)
                    permuted_list.remove(feature)
                    permuted_list.insert(new_pos, feature)
                    permutation_list.remove(index)
                    permutation_list.insert(new_pos, index)
            except ValueError:
                carb.log_error(f'feature reorder requested with invalid permutation map: {pemutation}')
                return

        else:
            carb.log_error(f'provided feature reorder with unsupported type: {type(permutation)}')
            return

        # if permutation is different from current order, change internal state
        # and send out event
        if permuted_list != self._feature_list:
            self._feature_list = permuted_list

            # push feature reorder event
            self.get_event_stream().push(FeatureChange.FEATURE_REORDER['id'], 0,
                                         payload={'change': FeatureChange.FEATURE_REORDER, 'permutation':
                                                  permutation_list})
            self.get_event_stream().pump()


    def get_feature_by_id(self, id: int) -> Optional[Feature]:
        '''Returns a feature from its id. This is particularly useful as carb.Events
        have the id of a feature as its sender
        '''
        for f in self._feature_list:
            if f.id == id:
                return f
        return None

    def get_feature_pos(self, feature: Feature) -> Optional[int]:
        '''Returns the position of the provided feature in the feature stack
        '''
        try:
            return self._feature_list.index(feature)
        except ValueError:
            return None

    def get_num_features(self):
        '''Returns the number of features in the current feature stack
        '''
        return len(self._feature_list)

    def get_filtered(self, predicate:Callable[[Feature],bool]):
        '''Returns a list of features that fulfill the given predicate
        '''
        return [f for f in self._feature_list if predicate(f)]

    # allows filtering for a type
    def get_by_type(self, feature_type: type, invert=False):
        '''Returns a list of features of a given type. If 'invert' is true,
        its complement is returned, so all features not of a given type.
        '''
        return self.get_filtered(lambda f:
                isinstance(f, feature_type) if not invert else not isinstance(f, feature_type))

    # allows filtering for a list of types
    def get_by_types(self, feature_types: List[type], invert=False):
        '''Returns a list of features of a given list of types. If 'invert' is
        true, its complement is returned, so all features of the given types
        '''
        return self.get_filtered(lambda f:
                np.array([isinstance(f, t) for t in feature_types]).any() if not invert else
                np.array([not isinstance(f, t) for t in feature_types]).all())

    def get_image_features(self):
        '''Returns a list of features of Image type
        '''
        return self.get_by_type(Image)

    def get_marker_features(self):
        '''Returns a list of features of Marker type
        '''
        return self.get_by_type(Marker)

    def get_volume_features(self):
        '''Returns a list of features of Volume type
        '''
        return self.get_by_type(Volume)

    def get_light_features(self):
        '''Returns a list of features of Light type
        '''
        return self.get_by_type(Light)

    def get_sun_features(self):
        '''Returns a list of features of Sun type
        '''
        return self.get_by_type(Sun)

    def get_curves_features(self):
        return self.get_by_type(Curves)

    # ========================================
    # Subscription Management
    # ========================================
    def get_event_stream(self):
        '''Returns the event stream for feature events. Any changes to the feature
        stack, or to property changes to its registered features will trigger events
        to be dispatched on this stream.
        '''
        return self._feature_list_stream

    def register_change(self, event_type: str | int, sender_id: int, payload: Optional[dict[str, Any]] = None, force_send: bool = False):
        '''Used by features to register changes.
        '''
        # first check if this feature is part of this api's list
        if not force_send and payload is not None and not self.get_feature_by_id(payload['id']):
            return

        self.get_event_stream().push(event_type, sender_id, payload)
        self.get_event_stream().pump()

    # ========================================
    # Protected
    # ========================================
    def _get_next_feature_id(self) -> int:
        tmp = self._feature_id_counter
        self._feature_id_counter += 1
        return tmp

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'FeatureChange', 'Feature' ]

from typing import Any, List, Callable, Optional, TypeVar
import datetime
import copy

class FeatureChange:
    FEATURE_ADD =       {'name':'FeatureAdd',    'id':1}
    FEATURE_REMOVE =    {'name':'FeatureRemove', 'id':2}
    FEATURE_CLEAR =     {'name':'FeatureClear',  'id':3}
    FEATURE_REORDER =   {'name':'FeatureReorder','id':4}
    PROPERTY_CHANGE =   {'name':'PropertyChange','id':5}

class Feature:
    feature_type = "Feature"

    def __init__(self, features_api: Optional["FeaturesAPI"] = None, feature_id: int = -1, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self._api = features_api
        self._id = feature_id
        self._name = 'unnamed'
        self._active = True
        self._time_coverage = None
        self._meta = {}

    @property
    def id(self):
        return self._id

    @property
    def type(self):
        return type(self).feature_type

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name: str):
        self._property_change('name', name)

    @property
    def active(self):
        return self._active

    @active.setter
    def active(self, active: bool):
        self._property_change('active', active)

    @property
    def time_coverage(self):
        return copy.copy(self._time_coverage)

    @time_coverage.setter
    def time_coverage(self, time_coverage: tuple[datetime, datetime]):
        self._property_change('time_coverage', time_coverage)

    @property
    def meta(self):
        return copy.deepcopy(self._meta)

    @meta.setter
    def meta(self, meta: dict):
        self._property_change('meta', meta)

    def _property_change(self, property_name: str, property_value: Any):
        internal_name = f'_{property_name}'
        cur_property_value = getattr(self, internal_name)

        change = False
        # for numpy arrays, we need to check through 'all()'
        import numpy as np
        if type(cur_property_value) != type(property_value):
            change = True
        elif isinstance(cur_property_value, np.ndarray):
            change = (cur_property_value != property_value).any()
        else:
            change = cur_property_value != property_value

        if change:
            old = cur_property_value
            setattr(self, internal_name, property_value)
            self._register_change(FeatureChange.PROPERTY_CHANGE,
                                  payload={'property': property_name, 'old_value': old, 'new_value': property_value})

    def _register_change(self, change_type: dict[str, str | int], payload: dict[str, Any] = {}, force_send: bool = False):
        if self._api:
            self._api.register_change(
                event_type=change_type['id'],
                sender_id=self._id,
                payload={
                    'feature_type': self.feature_type,
                    'id': self._id,
                    'change': change_type} | payload,
                force_send=force_send)

    def time_coverage_extend_to_include(self, start: datetime, end: datetime):
        '''Update time_coverage to include interval from `start` to `end`'''
        if self._time_coverage is None:
            self._time_coverage = (start, end)
        else:
            if start > self._time_coverage[0]:
                start = self._time_coverage[0]
            if end < self._time_coverage[1]:
                end = self._time_coverage[1]
            # this will trigger the property change event
            self.time_coverage = (start, end)

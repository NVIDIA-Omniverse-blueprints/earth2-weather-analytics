# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['Extension', 'get_ext']

from functools import partial

import omni.kit.app
import omni.ext
import omni.ui as ui

import carb
import carb.events
import carb.settings
import carb.tokens

from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features_api as features_api_module
import omni.earth_2_command_center.app.core.time_manager as time_manager_module
from omni.earth_2_command_center.app.globe_view import get_globe_view

from .custom_feature import CustomFeature
from .custom_feature_delegate import CustomFeatureDelegate

# we can use this to get access to the global instance of our extension
_ext = None
def get_ext():
    global _ext
    return _ext

class Extension(omni.ext.IExt):
    def on_startup(self, ext_id):
        # first we set the global instance to this one
        global _ext
        _ext = self

        # we store the extension id in case we need it
        self._ext_id = ext_id

        # we get the carb settings interface
        settings = carb.settings.get_settings()
        print(f'Extension Id: {ext_id}')
        example_setting = settings.get_as_bool("/exts/omni.earth_2_command_center.app.example_extension/example_setting")
        # we use a warning here just to make this easy to find in the logs
        # for production code, info-level logging might be more appropriate
        carb.log_warn(f'Example Setting: {example_setting}')

        # add a new feature
        features_api = get_state().get_features_api()
        self._feature = features_api.create_feature(CustomFeature)
        self._feature.name = 'Custom Feature'
        features_api.add_feature(self._feature)

        # register our feature type
        get_globe_view().register_feature_type_delegate(CustomFeature, CustomFeatureDelegate)

        # register to changes to features
        feature_event_stream = get_state().get_features_api().get_event_stream()
        #self._subscription = feature_event_stream.create_subscription_to_pop(self._on_feature_event)

        self._time_manager = get_state().get_time_manager()
        self._time_subscription = \
                self._time_manager.get_utc_event_stream().create_subscription_to_pop(self._on_utc_time_event)

    def on_shutdown(self): # pragma: no cover
        # set global instance to None
        global _ext
        _ext = None

        # no event callbacks from now on
        #self._subscription.unsubscribe()
        self._time_subscription.unsubscribe()

        # unregister our feature type
        get_globe_view().unregister_feature_type_delegate(CustomFeature, CustomFeatureDelegate)

        # remove our feature if it's still present
        if self._feature:
            features_api = get_state().get_features_api()
            features_api.remove_feature(self._feature)
            self._feature = None

    # ========================================
    # Private Methods
    # ========================================
    # callback from viewports on feature events
    def _on_viewport_feature_event(self, event, viewport):
        carb.log_warn(f'viewport callback: {viewport}, stage: {viewport.usd_stage}')

    # callback on feature events. we use this to keep our internal data in sync
    def _on_feature_event(self, event):
        if event.sender != self._feature.id:
            # not ours, early out
            return

        features_api = get_state().get_features_api()
        change = event.payload['change']
        feature_type = event.payload['feature_type']

        # all features were cleared
        if change['id'] == features_api_module.FeatureChange.FEATURE_CLEAR['id']:
            self._feature = None

        # add feature has been removed
        elif change['id'] == features_api_module.FeatureChange.FEATURE_REMOVE['id']:
            self._feature = None

        # check if active state has changed so we can propagate it to the underlying dynamic texture
        elif change['id'] == features_api_module.FeatureChange.PROPERTY_CHANGE['id'] and event.payload['property'] == 'active':
            old_value = event.payload['old_value']
            new_value = event.payload['new_value']
            carb.log_warn(f'Active Property was set from: {old_value} to: {new_value}')

    # callback on timeline events
    def _on_utc_time_event(self, event):
        if event.type == time_manager_module.UTC_START_TIME_CHANGED:
            carb.log_warn(f'Cur UTC Start Time: {self._time_manager.utc_start_time}')
        elif event.type == time_manager_module.UTC_END_TIME_CHANGED:
            carb.log_warn(f'Cur UTC End Time: {self._time_manager.utc_end_time}')
        elif event.type == time_manager_module.UTC_CURRENT_TIME_CHANGED:
            carb.log_warn(f'Cur UTC: {self._time_manager.utc_time}')

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
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence, MosaicTimestampedSequence, DiamondTimestampedSequence
import omni.earth_2_command_center.app.core.features_api as features_api_module

import omni.earth_2_command_center.app.test_sequence.blue_marble_sequences as blue_marble_sequences
import omni.earth_2_command_center.app.test_sequence.corr_diff_sequences as corr_diff_sequences
import omni.earth_2_command_center.app.test_sequence.diamond_sequences as diamond_sequences
import omni.earth_2_command_center.app.test_sequence.twc_sequences as twc_sequences
import omni.earth_2_command_center.app.test_sequence.meteoswiss_sequences as meteoswiss_sequences
import omni.earth_2_command_center.app.test_sequence.metadata_sequences as metadata_sequences

import numpy as np

_ext = None
def get_ext():
    global _ext
    return _ext

class Extension(omni.ext.IExt):
    def on_startup(self, ext_id):
        global _ext
        _ext = self

        self._ext_id = ext_id
        self._registered_test_sequences = []
        self._sequences = []
        self._next_idx = 0
        self._registered_names = []

        settings = carb.settings.get_settings()

        feature_event_stream = get_state().get_features_api().get_event_stream()
        self._subscription = feature_event_stream.create_subscription_to_pop(self._on_feature_event)
        self._time_manager = get_state().get_time_manager()

        # get the extension manager
        ext_manager = omni.kit.app.get_app_interface().get_extension_manager()
        feature_properties_ext_name = 'omni.earth_2_command_center.app.window.feature_properties'

        # register callbacks for when feature properties window is enabled/disabled
        # if the extension is already loaded, the callback is triggered immediately
        self._feature_properties_hook = ext_manager.subscribe_to_extension_enable(
                self._on_feature_properties_enable,
                self._on_feature_properties_disable,
                feature_properties_ext_name)

        # Blue Marble Test Sequences
        blue_marble_enabled = settings.get_as_bool("/exts/omni.earth_2_command_center.app.test_sequence/enable_blue_marble")
        if blue_marble_enabled:
            self.register_test_sequence('Add Blue Marble Clouds Sample',
                    partial(blue_marble_sequences.add_blue_marble_clouds_callback, self))
            self.register_test_sequence('Add Blue Marble Wind Sample',
                    partial(blue_marble_sequences.add_blue_marble_wind_callback, self))

        # CorrDiff Test Sequences
        corr_diff_sample_enabled = settings.get_as_bool("/exts/omni.earth_2_command_center.app.test_sequence/enable_corr_diff_sample")
        if corr_diff_sample_enabled:
            self.register_test_sequence('Add ERA5 Wind Sample', partial(corr_diff_sequences.add_era5windmag_callback, self))
            self.register_test_sequence('Add CorrDiff Sample',  partial(corr_diff_sequences.add_corr_diff_callback, self))

        # Diamond Test Sequences
        icon_blue_marble_enabled = settings.get_as_bool("/exts/omni.earth_2_command_center.app.test_sequence/enable_icon_blue_marble")
        if icon_blue_marble_enabled:
            self.register_test_sequence('Add ICON Blue Marble Wind Magnitude', partial(diamond_sequences.add_diamond_sequence_callback, self, 'sfcwind'))
            self.register_test_sequence('Add ICON Blue Marble Clouds', partial(diamond_sequences.add_diamond_sequence_callback, self, 'cloud'))

        # TWC Test Sequences
        #self.register_test_sequence('Add TWC Temperature Sample', partial(twc_sequences.add_twc_sequence_t2m_callback, self))
        #self.register_test_sequence('Add TWC Wind Speed Sample', partial(twc_sequences.add_twc_sequence_ws10_callback, self))

        # MeteoSwiss Sequences
        #self.register_test_sequence('Add MeteoSwiss Cloud Coverage Sample',
        #                            partial(meteoswiss_sequences.add_meteoswiss_sequence_callback, self))

        self.register_test_sequence('Add Features from MetaData file',
                                    partial(metadata_sequences.add_from_meta_json_callback, self))
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.register_action(self._ext_id, 'e2cc.add_from_file', \
                partial(metadata_sequences.add_from_meta_json_callback, self), \
                'Add from File', 'Read Features from Metadata File')

    # XXX: excluded from test coverage as fastShutdown seems to be on during testing
    # and thus it will never on_shutdown
    def on_shutdown(self): # pragma: no cover
        global _ext
        _ext = None

        self._feature_properties_hook = None
        self._unregister_add_callbacks()
        self._subscription.unsubscribe()
        self._time_manager = None
        self._registered_test_sequences = []

        features_api = get_state().get_features_api()
        for s,f in self._sequences:
            features_api.remove_feature(f)
        self._sequences = None

        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.deregister_all_actions_for_extension(self._ext_id)

    def add_sequence(self, seq, feature):
        for s,f in self._sequences:
            if s == seq:
                # already present...
                return
        self._sequences.append((seq, feature))

    def get_next_idx(self):
        idx = self._next_idx
        self._next_idx += 1
        return idx

    def register_test_sequence(self, name, callback):
        self._registered_test_sequences.append((name, callback))
        if self._is_feature_properties_enabled():
            self._register_add_callback(name, callback)

    def unregister_test_sequence(self, name, callback):
        self._registered_test_sequences.remove((name, callback))
        if self._is_feature_properties_enabled():
            self._unregister_add_callback(name, callback)

    # ========================================
    # Private Methods
    # ========================================
    def _is_feature_properties_enabled(self):
        # get the extension manager
        ext_manager = omni.kit.app.get_app_interface().get_extension_manager()
        feature_properties_ext_name = 'omni.earth_2_command_center.app.window.feature_properties'
        return ext_manager.is_extension_enabled(feature_properties_ext_name)

    def _on_feature_properties_enable(self, ext_id:str):
        # register to feature properties ui
        for name, callback in self._registered_test_sequences:
            self._register_add_callback(name, callback)

    def _register_add_callback(self, name, callback):
        from omni.earth_2_command_center.app.window.feature_properties import get_instance
        feature_properties = get_instance()
        feature_properties.register_feature_type_add_callback(name, callback)
        self._registered_names.append(name)

    def _on_feature_properties_disable(self, ext_id:str):
        self._unregister_add_callbacks()

    def _unregister_add_callbacks(self):
        if not self._is_feature_properties_enabled():
            return

        from omni.earth_2_command_center.app.window.feature_properties import get_instance
        feature_properties = get_instance()
        for name in self._registered_names:
            feature_properties.unregister_feature_type_add_callback(name)
        self._registered_names = []

    # callback on feature events. we use this to keep our internal data in sync
    def _on_feature_event(self, event):
        features_api = get_state().get_features_api()
        change = event.payload['change']
        feature_type = event.payload['feature_type']

        # all features were cleared
        if change['id'] == features_api_module.FeatureChange.FEATURE_CLEAR['id']:
            # we want to release these dynamic textures
            for seq,img in self._sequences:
                if isinstance(seq, DiamondTimestampedSequence):
                    get_state().get_icon_helper().unregister_diamond_list(img, seq.tex_list())
                seq.release()
            self._sequences = []

        # add feature has been removed
        elif change['id'] == features_api_module.FeatureChange.FEATURE_REMOVE['id']:
            # was it one of 'ours'?
            sender_id = event.sender
            for i,(seq,img) in enumerate(self._sequences):
                if sender_id == img.id:
                    if isinstance(seq, DiamondTimestampedSequence):
                        get_state().get_icon_helper().unregister_diamond_list(img, seq.tex_list())
                    del self._sequences[i]
                    seq.release()
                    break

        # check if active state has changed so we can propagate it to the underlying dynamic texture
        elif change['id'] == features_api_module.FeatureChange.PROPERTY_CHANGE['id'] and event.payload['property'] == 'active':
            # was it one of 'ours'?
            sender_id = event.sender
            for i,(seq,img) in enumerate(self._sequences):
                if sender_id == img.id:
                    if isinstance(seq, MosaicTimestampedSequence):
                        for t in seq.tex_list():
                            t.active = event.payload['new_value']
                    else:
                        seq.tex.active = event.payload['new_value']

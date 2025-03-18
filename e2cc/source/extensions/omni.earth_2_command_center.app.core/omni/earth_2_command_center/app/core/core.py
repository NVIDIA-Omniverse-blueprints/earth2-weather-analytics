# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from __future__ import annotations
__all__ = ['get_state', 'State']

import omni.kit.app
import omni.ext

import carb
import carb.events
import carb.settings
import carb.tokens

from .features_api import *
from .time_manager import *
from .icon_helper import *

_state = None
def get_state() -> State:
    return _state

class GlobeViewEventType:
    ViewChanged = 1

class State(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._ext_id = ext_id
        self._sender_id = hash("State") & 0xFFFFFFFF

        self._apply_settings()

        self._features_api = FeaturesAPI()

        events_interface = carb.events.acquire_events_interface()
        self._stream_globe_view = events_interface.create_event_stream()

        self._time_manager = TimeManager()
        self._icon_helper = ICONHelper(ext_id)

        global _state
        _state = self

    def _apply_settings(self):
        settings = carb.settings.get_settings()
        tokens = carb.tokens.get_tokens_interface()
        #stage_setting = settings.get_as_string("/exts/omni.earth_2_command_center.app.setup/stage")
        #self._stage_path = tokens.resolve(stage_setting)

    def get_globe_view_event_stream(self):
        return self._stream_globe_view

    def get_features_api(self):
        return self._features_api

    def get_time_manager(self):
        return self._time_manager

    def get_icon_helper(self):
        return self._icon_helper

    # XXX: excluded from test coverage as fastShutdown seems to be on during testing
    # and thus it will never on_shutdown
    def on_shutdown(self): # pragma: no cover
        global _state
        _state = None
        self._time_manager = None
        self._stream_globe_view = None

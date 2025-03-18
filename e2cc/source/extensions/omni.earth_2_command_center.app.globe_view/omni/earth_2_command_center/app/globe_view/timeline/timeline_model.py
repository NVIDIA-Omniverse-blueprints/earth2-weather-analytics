# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import carb

import omni.ext
import omni.kit.app
import omni.ui as ui

from omni.timeline import TimelineEventType

import omni.earth_2_command_center.app.core as core

class TimelinePlayModel(ui.AbstractValueModel):
    def __init__(self):
        super().__init__()
        self._time_manager = core.get_state().get_time_manager()
        self._timeline_sub = self._time_manager.get_timeline_event_stream().create_subscription_to_pop(self._on_timeline_event)
        self._timeline = self._time_manager.get_timeline()

    def __del__(self):
        self.destroy()

    def destroy(self):
        self._timeline_sub.unsubscribe()
        self._timeline_sub = None
        self._time_manager = None

    def _on_timeline_event(self, evt):
        value = int(evt.type)
        if value in [int(TimelineEventType.PLAY), int(TimelineEventType.STOP), int(TimelineEventType.PAUSE)]:
            self._value_changed()

    def get_value_as_bool(self):
        return self._timeline.is_playing()

    def set_value(self, value: bool):
        if value:
            self._timeline.play()
        else:
            self._timeline.pause()

class TimelineCurrentModel(ui.AbstractValueModel):
    def __init__(self):
        super().__init__()
        self._time_manager = core.get_state().get_time_manager()
        self._timeline_sub = self._time_manager.get_timeline_event_stream().create_subscription_to_pop(self._on_timeline_event)
        self._timeline = self._time_manager.get_timeline()
        self._value_changed()

    def __del__(self):
        self.destroy()

    def destroy(self):
        self._timeline_sub = None
        self._timeline = None

    def _on_timeline_event(self, evt):
        value = int(evt.type)
        if value in [int(TimelineEventType.CURRENT_TIME_CHANGED), int(TimelineEventType.CURRENT_TIME_TICKED)]:
            self._value_changed()

    def get_value_as_float(self):
        return self._timeline.get_current_time()

    def set_value(self, value: float):
        try:
            v = float(value)
        except ValueError:
            return

        if self._timeline.get_current_time() != value:
            self._timeline.set_current_time(v)

    def begin_edit(self) -> None:
        pass

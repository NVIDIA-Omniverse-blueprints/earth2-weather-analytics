# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ["TimelineMinibar"]

import carb

import omni.timeline
import omni.ui as ui

import omni.earth_2_command_center.app.core as core

from .timeline_model import *

from ..style import PLAYBACK_PANEL, _LIGHT, _LIGHT_A, _BLUE, _BLUE_A


HOURS_IN_DAY = 24
MINUTES_IN_HOURS = 60
BUTTON_SIZE = 28

class TimelineMinibar:
    """The class that represents the timeline minibar"""
    def __init__(self, default_time:float = 0.0):
        self.__root = None
        # self._speed_button = None
        self._cur_speed_index = 2
        self._speeds = ["speed_1x", "speed_2x", "speed_4x", "speed_8x"]
        self._tps = [120.0, 60.0, 30.0, 15.0]  # hardcoded times per second
        self._slider_height = 42 # defined in the specs for E2 demo
        self._time_manager = core.get_state().get_time_manager()
        self._timeline = omni.timeline.get_timeline_interface()
        self._timeline.set_looping(True)
        self._timeline_subscription = self._time_manager.get_timeline_event_stream().create_subscription_to_pop(self._on_time_event)
        self._utc_time_subscription = self._time_manager.get_utc_event_stream().create_subscription_to_pop(self._on_utc_event)

        self._play_model = TimelinePlayModel()
        self._cur_model = TimelineCurrentModel()

        self.__root = ui.Frame()
        self.__root.set_build_fn(self._build_fn)

    def destroy(self): # pragma: no cover
        self._timeline_subscription.unsubscribe()
        self._timeline_subscription = None

        # self._speed_button = None
        self._timeline = None

        self._start_widget = None
        self._end_widget = None
        self._slider = None

        if self.__root:
            self.__root = None
        if self._play_model:
            self._play_model.destroy()
            self._play_model = None
        if self._cur_model:
            self._cur_model.destroy()
            self._cur_model = None

    def _build_fn(self):
        #self._timeline.set_time_codes_per_second(self._tps[self._cur_speed_index])
        with ui.HStack(height=0, style=PLAYBACK_PANEL):
            with ui.ZStack(width=500, height=self._slider_height , content_clipping=True):
                ui.Rectangle()
                with ui.HStack(spacing=2):
                    ui.Spacer(width=10)
                    # play button
                    ui.ToolButton(
                        image_width=BUTTON_SIZE,
                        iamge_height=BUTTON_SIZE,
                        width=0,
                        model=self._play_model,
                        name="play"
                    )
                    # # playback speed control button
                    # self._speed_button = ui.Button(
                    #     image_width=BUTTON_SIZE,
                    #     iamge_height=BUTTON_SIZE,
                    #     width=0,
                    #     name=self._speeds[self._cur_speed_index],
                    #     clicked_fn=self._on_speed_clicked,
                    # )
                    with ui.VStack():
                        ui.Spacer(height=ui.Percent(10))
                        with ui.ZStack(content_clipping=True, height=ui.Percent(80), seperate_window=True):
                            # Time Coverage
                            with ui.VStack(enabled=False):
                                ui.Spacer(height=ui.Percent(90))

                                # get features and total time
                                features = [f for f in core.get_state().get_features_api().get_features()
                                        if f.active and f.time_coverage is not None]
                                time_manager = core.get_state().get_time_manager()
                                start_time = time_manager.utc_start_time
                                end_time = time_manager.utc_end_time
                                total_duration = end_time-start_time

                                if features:
                                    # FloatSlider doesn't go to the edges...
                                    with ui.HStack():
                                        ui.Spacer(width=ui.Percent(1))
                                        with ui.ZStack():
                                            # for each feature, we draw a rectangle
                                            import numpy as np
                                            for f in features:
                                                a,b = f.time_coverage
                                                if (b-a).total_seconds() <= 0:
                                                    continue
                                                start = np.clip((a-start_time)/total_duration, 0, 1) if total_duration.total_seconds() > 0 else 0
                                                end =   np.clip((b-start_time)/total_duration, 0, 1) if total_duration.total_seconds() > 0 else 0
                                                # make sure segments are reasonably visible
                                                min_width = 1e-2
                                                if end-start < min_width:
                                                    mid = max(0.5*min_width, min(1.0-0.5*min_width, 0.5*(end+start)))
                                                    start = np.clip(mid-0.5*min_width, 0, 1)
                                                    end = np.clip(start+min_width, 0, 1)

                                                with ui.HStack():#height=ui.Percent(20)):
                                                    ui.Spacer(width=ui.Percent(start*100))
                                                    ui.Rectangle(width=ui.Percent((end-start)*100), style = {'background_color': _BLUE})
                                                    ui.Spacer()
                                        ui.Spacer(width=ui.Percent(1))

                            # Labels
                            with ui.HStack():
                                ui.Spacer(width=ui.Percent(40))
                                self._time_label = ui.Label("", width=0)
                                ui.Spacer(width=15)
                                self._date_label = ui.Label("", width=120, name="date")

                            # Slider
                            self._time_slider = ui.FloatSlider(
                                name="timeline",
                                model=self._cur_model,
                                min=0.0,
                                max=1.0,
                                precision=2,
                                step = 1.0/self._tps[self._cur_speed_index],
                                width=ui.Percent(100),
                                style={"color":0x00000000} # hide the float number
                                )
                        ui.Spacer(height=ui.Percent(10))

                    #TODO: organize and add date model
                    ui.Spacer(width=15)
                    #self._time_label = ui.Label("", width=0)
                    #ui.Spacer(width=15)
                    #self._date_label = ui.Label("", width=120, name="date")
                    #ui.Spacer(width=15)

                    self._cur_model.add_value_changed_fn(self._on_current_changed)

                    self._update_slider_range()
                    self._update_datetime()

    def _update_datetime(self) -> None:
        if not self.__root:
            return

        utc_time = self._time_manager.current_utc_time
        if isinstance(self._time_label, ui.Label):
            self._time_label.text = utc_time.strftime("%H:%M")#str(current_time) + " UTC"
        if isinstance(self._date_label, ui.Label):
            self._date_label.text = utc_time.strftime("%h %d, %Y")#str(current_time) + " UTC"

    def _on_time_event(self, event):
        if omni.timeline.TimelineEventType(event.type) in [
                omni.timeline.TimelineEventType.START_TIME_CHANGED,
                omni.timeline.TimelineEventType.END_TIME_CHANGED,
                omni.timeline.TimelineEventType.TIME_CODE_PER_SECOND_CHANGED]:
            self.__root.rebuild()

    def _on_utc_event(self, event):
        if event in [
                core.time_manager.UTC_START_TIME_CHANGED,
                core.time_manager.UTC_END_TIME_CHANGED,
                core.time_manager.UTC_PER_SECOND_CHANGED ]:
            self.__root.rebuild()

    def _on_current_changed(self, model):
        self._update_slider_range()
        self._update_datetime()

    def _update_slider_range(self):
        if not self.__root:
            return

        start = self._time_manager.playback_start_time
        end = self._time_manager.playback_end_time
        self._time_slider.min = start
        self._time_slider.max = end
        self._time_slider.step = 1.0/self._tps[self._cur_speed_index]

    # def _on_speed_clicked(self):
    #     next_index = (self._cur_speed_index + 1) % len(self._speeds)
    #     self._cur_speed_index = next_index
    #     self._speed_button.name = self._speeds[next_index]
    #     self._timeline.set_time_codes_per_second(self._tps[next_index])

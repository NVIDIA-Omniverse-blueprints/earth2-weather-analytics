# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ["DatePickerWidget"]

import omni.ui as ui
from .preset_dates_model import *

from ..style import DATE_PANEL

class DatePickerWidget:
    def __init__(self, minibar):
        self._minibar = minibar
        self.__root = None
        self._preset_dates = ["December 7, 1972", "June 22, 2023"]
        self._preset_date_model = PresetDateModel()
        self._preset_date_model.set_toggled_fn(self.on_date_preset_toggled)
        self._slider_height = 42 # defined in the specs for E2 demo
        self._cursor_radius = self._slider_height / 2 - 1
        self._num_decades = 13

        self._build_fn()


    def _build_fn(self):
        self.__root = ui.HStack(height=0, style=DATE_PANEL)
        with self.__root:
            with ui.ZStack(width=800, height=self._slider_height, content_clipping=True):
                # base rectangle
                ui.Rectangle()

                # timeline
                with ui.HStack(spacing=2):
                    ui.Spacer(width=15)
                    self._begin_label = ui.Label("1960", width=0)
                    ui.Spacer(width=15)
                    # timeline background lines
                    with ui.ZStack():
                        with ui.HStack(spacing=2):
                            ui.Line(name="timeline", alignment=ui.Alignment.V_CENTER)
                        # timeline split lines
                        with ui.HStack(spacing=2):
                            ui.Spacer()
                            for i in range(self._num_decades):
                                with ui.VStack(height=self._slider_height):
                                    ui.Spacer(width=2)
                                    ui.Line(name="timeline", alignment=ui.Alignment.H_CENTER)
                                    ui.Spacer(width=2)
                            ui.Spacer()
                    ui.Spacer(width=15)
                    self._end_label = ui.Label("2100", width=0)
                    ui.Spacer(width=15)
                with ui.VStack():
                    ui.Spacer(height=ui.Percent(25))
                    # button overlays
                    with ui.HStack(spacing=2):
                        ui.Spacer(width=130) # TODO: hardcoded value
                        self.c1 = ui.Circle(
                            name="scenario_1",
                            radius=self._cursor_radius,
                            width=self._cursor_radius,
                            height=self._cursor_radius,
                            alignment=ui.Alignment.CENTER,
                        )
                        self.c1.set_mouse_pressed_fn(lambda *_, b=self.c1: self._set_preset_scenario(b))
                        self._preset_date_model.append(self.c1)

                        # NOTE: Removed for demo @gamato
                        # ui.Spacer(width=200) # TODO: hardcoded value
                        # self.c2 = ui.Circle(
                        #     name="scenario_2",
                        #     radius=self._cursor_radius,
                        #     width=self._cursor_radius,
                        #     height=self._cursor_radius,
                        #     alignment=ui.Alignment.CENTER,
                        # )
                        # self.c2.set_mouse_pressed_fn(lambda *_, b=self.c2: self._set_preset_scenario(b))
                        # self._preset_date_model.append(self.c2)
                    ui.Spacer(height=ui.Percent(25))

        self._preset_date_model.set_active_button(self.c1)

    # FIXME: mouse press not registering
    def _set_preset_scenario(self, scenario):
        self._preset_date_model.set_active_button(scenario)

    def on_date_preset_toggled(self):
        active_btn = self._preset_date_model.get_active_button()
        date = self.get_date_from_button(active_btn)
        self.update_date_on_timeline(date)

    # TODO: not implemented
    def get_date_from_button(self, button):
        return "December 7, 1972"

    def update_date_on_timeline(self, date):
        self._minibar.update_date(date)

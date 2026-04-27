# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

__all__ = [ 'MainWindow' ]

import asyncio
import logging
from pathlib import Path
import datetime
from dateutil.parser import parse
import threading
from pydantic import ValidationError

import carb
import carb.settings
import omni.ui as ui

import omni.kit.async_engine as async_engine
import omni.kit.app as kit_app
from omni.kit.window.filepicker.datetime import DateWidget, TimeWidget, TimezoneWidget

def is_valid_iso_timestamp(timestamp_string):
    try:
        parse(timestamp_string)
        return True
    except ValueError:
        return False

class MainWindow(ui.Window):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frame.set_build_fn(self._build)
        self._job = None

    def _build(self):
        lineheight = 20
        with ui.VStack(style={'Button.Label:disabled': {'color': ui.color.grey}}):
            with ui.HStack(height=lineheight):
                ui.Label('Widgets: ', width=80, alignment=ui.Alignment.LEFT_CENTER)
                self._date_widget = DateWidget()
                ui.Spacer(width=10)
                self._time_widget = TimeWidget()
                ui.Spacer(width=10)
                self._timezone_widget = TimezoneWidget()
            ui.Spacer()
            ui.Separator()
            ui.Spacer()
            with ui.HStack(height=lineheight):
                self._button_cancel = ui.Button('Cancel')
                self._button_cancel.set_clicked_fn(self._cancel)
                self._button = ui.Button('Go!')
                self._button.set_clicked_fn(self._go)

    def _go(self):
        print('Go!')
        from_widgets = datetime.datetime(
                self._date_widget.model.year, self._date_widget.model.month, self._date_widget.model.day,
                self._time_widget.model.hour, self._time_widget.model.minute, self._time_widget.model.second,
                tzinfo=self._timezone_widget.model.timezone)
        print(f'From Widgets: {from_widgets}')

        from omni.earth_2_command_center.app.earth2_blueprint import get_ext
        runner = get_ext().get_pieline_runner()
        async def run():
            #if self._job is not None:
            return await runner.run_async()
        self._cancel()
        self._job = async_engine.run_coroutine(run())

    def _cancel(self):
        if self._job is not None and not self._job.done():
            carb.log_warn('canceling previous task')
            self._job.cancel()

    def destroy(self):
        carb.log_warn('MainWindow destroy()')
        self.frame = None

    def __del__(self):
        self.destroy()
        self._job = None


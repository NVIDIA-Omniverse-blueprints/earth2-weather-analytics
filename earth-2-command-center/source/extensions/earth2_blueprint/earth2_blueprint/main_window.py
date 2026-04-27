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
import copy

import carb
import carb.settings
import omni.ui as ui

import omni.kit.async_engine as async_engine
import omni.kit.app as kit_app
from omni.kit.window.filepicker.datetime import DateWidget, TimeWidget, TimezoneWidget
from omni.kit.window.popup_dialog import MessageDialog

def is_valid_iso_timestamp(timestamp_string):
    try:
        parse(timestamp_string)
        return True
    except ValueError:
        return False

class ProgressWidget(ui.ZStack):
    def __init__(self, model=None, *args, **kwargs):
        self._status = kwargs.get("status", '')
        self._style = kwargs.get("style", {}) | {
                        'ProgressRectangle':{'background_color':ui.color(0.1, 0.3, 0.8)},
                        'ProgressRectangle:disabled':{'background_color':ui.color.transparent},
                        #'Label':{'color':ui.color.white},
                        #'Label:disabled':{'color':ui.color.transparent}}
                        }
        if 'style' in kwargs:
            kwargs.pop('style')

        self._bar_width = ui.Percent(10)
        super().__init__(*args, **kwargs, style=self._style)

        self.model = model if model is not None else ui.SimpleFloatModel(0)
        self.model.add_value_changed_fn(self._on_changed)

        with self:
            # background rectangle
            ui.Rectangle(width=ui.Percent(100))
            with ui.HStack():
                self._progress_bar = [
                        ui.Rectangle(width=ui.Percent(0)),
                        ui.Rectangle(width=ui.Percent(self._bar_width),
                                     style_type_name_override='ProgressRectangle',
                                     ),
                        ui.Rectangle(width=ui.Percent(90))]#100-self._bar_width))]
            self.label = ui.Label(self._status, alignment=ui.Alignment.CENTER)

    def _on_changed(self, change):
        # TODO: update visuals
        cur_value = self.model.get_value_as_float()
        a = max(0, min(100, cur_value))
        b = max(0, min(100, cur_value+self._bar_width))
        w0 = a
        w1 = b-a
        w2 = max(0, 100-b)
        self._progress_bar[0].width = ui.Percent(w0)
        self._progress_bar[1].width = ui.Percent(w1)
        self._progress_bar[2].width = ui.Percent(w2)

    def destroy(self):
        carb.log_warn('destroying')
        super().destroy()

    @property
    def status(self):
        return self.label.text

    @status.setter
    def status(self, s):
        self.label.text = str(s)

    def __del__(self):
        self.destroy()

class VariableFrame():
    def __init__(self, active:bool, name:str, varname:str, colormap:str, min_value:float, max_value:float,
                 output_gamma:float=1, label_width:float=120, **kwargs):
        self.frame = ui.CollapsableFrame(name, height=0, collapsed=not active, enabled=False)
        self.frame.set_build_header_fn(self._build_header)

        self._active_model = ui.SimpleBoolModel(active)
        def toggle_active(model):
            self.frame.collapsed = not model.get_value_as_bool()
        self._active_model.add_value_changed_fn(toggle_active)

        self._name = name
        self._varname = varname
        self._min_value_model = ui.SimpleFloatModel(min_value)
        self._max_value_model = ui.SimpleFloatModel(max_value)
        self._output_gamma_model = ui.SimpleFloatModel(output_gamma)

        self._colormaps = ['afmhot', 'viridis', 'plasma']
        if colormap not in self._colormaps:
            self._colormaps.append(colormap)

        with self.frame:
            with ui.VStack(spacing=2, enabled=True):
                with ui.HStack():
                    ui.Label('Min Value: ', width=label_width)
                    ui.FloatField(self._min_value_model, width=60)
                    ui.Spacer(width=10)
                    ui.Label('Max Value: ', width=label_width)
                    ui.FloatField(self._max_value_model, width=60)
                with ui.HStack():
                    ui.Label('Colormap: ', width=label_width)
                    self._colormap_widget = ui.ComboBox(0, *self._colormaps)
                    self._colormap_widget.model.get_item_value_model().set_value(self._colormaps.index(colormap))
                with ui.HStack():
                    ui.Label('Output Gamma: ', width=label_width)
                    ui.FloatSlider(self._output_gamma_model, min=0, max=2)
    @property
    def active(self):
        return self._active_model.get_value_as_bool()

    @property
    def name(self):
        return self._name

    @property
    def varname(self):
        return self._varname

    @property
    def min_value(self):
        return self._min_value_model.get_value_as_float()

    @property
    def max_value(self):
        return self._max_value_model.get_value_as_float()

    @property
    def colormap(self):
        current_index = self._colormap_widget.model.get_item_value_model().as_int
        return self._colormaps[current_index]

    @property
    def output_gamma(self):
        return self._output_gamma_model.get_value_as_float()

    def _build_header(self, collapsed, name):
        with ui.VStack():
            with ui.HStack(enabled=True, height=20):
                ui.CheckBox(self._active_model)
                ui.Label(name)
                ui.Spacer()
            ui.Separator(menu_compatibility=False)

    def destroy(self):
        pass

    def __del__(self):
        self.destroy()

class MainWindow(ui.Window):
    STATUS_NO_TASK = 'No task running'
    STATUS_TASK_RUNNING = 'Task running...'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, flags=ui.WINDOW_FLAGS_NO_CLOSE | ui.WINDOW_FLAGS_NO_RESIZE)
        self.frame.set_build_fn(self._build)
        self._job = None

    def _build(self):
        label_width = 120
        line_height = 20

        #selected_timestamp = (datetime.datetime.now()-datetime.timedelta(days=2)).replace(
        #        hour=12, minute=0, second=0, microsecond=0)
        selected_timestamp = datetime.datetime(2026, 3, 1, 12, 0)

        with ui.VStack(spacing=4, height=0, style={
            'Button.Label:disabled': {'color': ui.color.grey}}):
            ui.Label("Model Inputs:", style={"font":"${fonts}/OpenSans-SemiBold.ttf", "font_size": 20.0})#, alignment=ui.Alignment.CENTER)
            ui.Separator(menu_compatibility=False)
            with ui.HStack(height=line_height):
                ui.Label('Start Predication: ', width=label_width)
                self._date_widget = DateWidget()
                self._date_widget.model.set_value(selected_timestamp.isoformat())
                self._date_widget.model.add_value_changed_fn(self._on_date_picked)
                ui.Spacer(width=20)
                self._time_widget = TimeWidget()
                self._time_widget.model.set_value(selected_timestamp.isoformat())
                #ui.Spacer(width=10)
                #self._timezone_widget = TimezoneWidget()
            with ui.HStack(height=line_height):
                ui.Label('Days to predict: ', width=label_width)
                self._num_days_widget = ui.IntSlider(min=1, max=12)
                self._num_days_widget.model.set_value(3)
            ui.Spacer(height=line_height)

            ui.Label("Model Outputs:", style={"font":"${fonts}/OpenSans-SemiBold.ttf", "font_size": 20.0})#, alignment=ui.Alignment.CENTER)
            ui.Separator(menu_compatibility=False)
            self._variables = [
                    VariableFrame(True, 'Temperature (t2m)', 't2m', 'cmo.thermal', 273.15-20, 273.15+35, .6),
                    VariableFrame(True, 'Mean Sea Level Pressure (msl)', 'msl', 'viridis', 98000, 105000, 1),
                    VariableFrame(True, 'Total Column Water Vapour (tcwv)', 'tcwv', 'greyscale', 0, 75, .3),
                    ]
            ui.Spacer(height=line_height)

            ui.Spacer()
            ui.Separator(menu_compatibility=False)
            with ui.VStack(spacing=0):
                self._progress_model = ui.SimpleFloatModel(0)
                self._progress = ProgressWidget(model=self._progress_model, status=MainWindow.STATUS_NO_TASK,
                                                height=line_height, enabled=False)
            ui.Separator(menu_compatibility=False)
            #ui.Spacer(height=line_height)

            with ui.HStack(height=line_height):
                self._button_cancel = ui.Button('Cancel', enabled=False)
                self._button_cancel.set_clicked_fn(self._cancel)
                self._button_go = ui.Button('Go!')
                self._button_go.set_clicked_fn(self._go)

    @property
    def date(self):
        cur_timestamp = datetime.datetime(
                self._date_widget.model.year, self._date_widget.model.month, self._date_widget.model.day,
                self._time_widget.model.hour, self._time_widget.model.minute, self._time_widget.model.second,
                )#tzinfo=self._timezone_widget.model.timezone)

        # round to 6hrs as this is a GFS requirement
        cur_timestamp = cur_timestamp.replace(
                hour=cur_timestamp.hour//6*6,
                minute=0, second=0, microsecond=0)
        return cur_timestamp

    def _is_valid_date(self, date):
        date = date.date()
        today = datetime.datetime.now().date()
        min_date = datetime.datetime(2021, 3, 23).date()
        max_date = (today-datetime.timedelta(days=1))
        error_msg = f'Date must be after {min_date} and before {max_date}'
        if date < min_date:
            carb.log_warn(f'{date} < {min_date}')
            return False, error_msg, min_date
        elif date > max_date:
            carb.log_warn(f'{date} > {max_date}')
            return False, error_msg, max_date-datetime.timedelta(days=1)
        return True,'',date

    def _on_date_picked(self, model):
        carb.log_warn(f'on date picked: {self.date}')
        valid, error_reason, suggested_date = self._is_valid_date(self.date)
        if not valid:
            carb.log_warn('creating message dialog')
            def ok_handler(dialog):
                dialog.hide()
                carb.log_warn(f'setting to suggested date: {suggested_date.isoformat()}')
                self._date_widget.model.set_value(suggested_date.isoformat())
            MessageDialog(title="Date Error",
                          warning_message=error_reason,
                          ok_handler=ok_handler,
                          disable_cancel_button=True).show()

    def _go(self):
        # get the active output variables
        active_vars = [v for v in self._variables if v.active]
        if not active_vars:
            def ok_handler(dialog):
                dialog.hide()
                return
            MessageDialog(title="No output variable selected",
                          warning_message="Select at least one output variable",
                          ok_handler=ok_handler,
                          disable_cancel_button=True).show()

        # get selected time and calculate the number of steps to produce
        prediction_start = self.date
        num_steps = self._num_days_widget.model.get_value_as_int()*4

        def get_input_params_dict_for_variable(v):
            return {f'{v.varname}_min_value':v.min_value,
                    f'{v.varname}_max_value':v.max_value}
        info = {}
        for v in active_vars:
            info[v.varname] = {
                    'name':v.name,
                    'varname':v.varname,
                    'colormap':v.colormap,
                    'min_value':v.min_value,
                    'max_value':v.max_value,
                    'output_gamma':v.output_gamma}

        self._cancel()
        input_params = {
                'selection':{'time':prediction_start.isoformat()},
                'n_steps':num_steps,
                }
        for v in active_vars:
            input_params |= get_input_params_dict_for_variable(v)

        from earth2_blueprint import get_ext
        runner = get_ext().get_pieline_runner()
        async def run(*args, **kwargs):
            return await runner.run_async(*args, **kwargs)

        self._job = async_engine.run_coroutine(run(
            input_params=input_params, variables=info))
        self._task_checker_job = async_engine.run_coroutine(self._task_checker())

    async def _task_checker(self):
        width = 10
        try:
            if self._job:
                done = False
                self._button_go.enabled = False
                self._button_cancel.enabled = True
                self._progress.enabled = True
                self.set_status(MainWindow.STATUS_TASK_RUNNING)
                cur_value = -10
                while not self._job.done():
                    cur_value = ((cur_value + 2 + width)%(100+width)) - width
                    self._progress_model.set_value(cur_value)
                    await asyncio.sleep(1/24)
        except:
            import traceback
            traceback.print_exc()
        finally:
            self._button_go.enabled = True
            self._button_cancel.enabled = False
            self._progress.enabled = False
            self.set_status(MainWindow.STATUS_NO_TASK)

    def _cancel(self):
        if self._job is not None and not self._job.done():
            carb.log_warn('canceling previous task')
            self._job.cancel()

    def destroy(self):
        carb.log_warn('MainWindow destroy()')

    def set_status(self, status):
        self._progress.status = str(status)

    def __del__(self):
        self.destroy()
        self._job = None


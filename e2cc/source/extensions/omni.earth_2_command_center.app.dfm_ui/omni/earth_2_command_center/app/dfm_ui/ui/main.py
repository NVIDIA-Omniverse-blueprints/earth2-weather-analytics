# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from datetime import datetime

import concurrent
import carb
import omni.earth_2_command_center.app.core as earth_core
from omni import ui
from omni.kit.window.filepicker.datetime import DateWidget, TimeWidget
from omni.kit.window.filepicker.datetime.calendar import DateModel
from omni.kit.window.filepicker.datetime.clock import TimeModel

from omni.earth_2_command_center.app.dfm.pipelines.gfs import GFSPipeline
from omni.earth_2_command_center.app.dfm.pipelines.era5 import ERA5Pipeline
from omni.earth_2_command_center.app.dfm.pipelines.fcn import FourCastNetPipeline
from omni.earth_2_command_center.app.dfm.pipelines.hrrr import HRRRPipeline
from omni.earth_2_command_center.app.dfm.pipelines.esri_topo import ESRITopoPipeline, SUPPORTED_ESRI_PROCESSING_MODES
from omni.earth_2_command_center.app.dfm.utils.constants import VARIABLE_LABELS
from omni.earth_2_command_center.app.dfm.utils.exceptions import InputVariableError, InputTimeRangeError

class ExtensionWindow:
    def __init__(self):

        # UI inputs
        self._date_widget = None
        self._time_widget = None
        self._variable_combo = None
        self._source_combo = None
        self._status_label = None
        self._fetch_button = None
        self._num_samples = None
        self._num_samples_slider = None
        self._esri_topo_combo = None

        # Pipeline object
        self._pipeline = None
        self._editor_window = None
        self._models = {}

    def shutdown(self):
        self._editor_window = None

    def hide(self):
        self._editor_window.visible = False

    def show(self):
        self._editor_window.visible = True

    def is_visible(self):
        return self._editor_window.visible

    def run_esri_pipeline(self):
        """Run ESRI DFM pipeline event"""
        # Check to see if theres a pipeline already running if so wait
        if self._pipeline is not None and not self._pipeline.done():
            carb.log_error("Pipeline already running!")
            self._status_label.text = "Pipeline Running"
            return

        # I know that there should be an easier way..
        mode = SUPPORTED_ESRI_PROCESSING_MODES[self._esri_topo_combo.model.get_item_value_model().get_value_as_int()]

        self._status_label.text = "Fetching ESRI Topo data"
        self._pipeline = ESRITopoPipeline.execute(processing=mode)
        self._pipeline.add_done_callback(self._pipeline_callback)


    def run(self):
        """Run DFM pipeline event"""
        # Check to see if theres a pipeline already running if so wait
        if self._pipeline is not None and not self._pipeline.done():
            carb.log_error("Pipeline already running!")
            self._status_label.text = "Pipeline Running"
            return

        # Parse input date time
        input_datetime = datetime(
            self._date_widget.model.year, self._date_widget.model.month, self._date_widget.model.day,
            self._time_widget.model.hour, self._time_widget.model.minute, self._time_widget.model.second)
        # Parse variable
        input_variable = self.variables[self._variable_combo.model.get_item_value_model().get_value_as_int()]

        num_samples = self._num_samples.as_int

        carb.log_info(f"Input date time {input_datetime.isoformat()}")
        carb.log_info(f"Input variable {input_variable}")
        # Just make sure this matches the order in source_labels
        try:
            match self._source_combo.model.get_item_value_model().get_value_as_int():
                case 0:
                    # Run GFS fetch
                    self._status_label.text = "Fetching GFS data"
                    self._pipeline = GFSPipeline.execute(input_variable, input_datetime, num_timesteps=num_samples+1)
                    self._pipeline.add_done_callback(self._pipeline_callback)
                case 1:
                    # Run ERA5 fetch
                    self._status_label.text = "Fetching ERA5 data"
                    self._pipeline = ERA5Pipeline.execute(input_variable, input_datetime, num_timesteps=num_samples+1)
                    self._pipeline.add_done_callback(self._pipeline_callback)
                case 2:
                    # Run FourCastNet fetch
                    self._status_label.text = "Fetching FCN data"
                    self._pipeline = FourCastNetPipeline.execute(input_variable, input_datetime, num_timesteps=num_samples)
                    self._pipeline.add_done_callback(self._pipeline_callback)
                case 3:
                    # Run HRRR fetch
                    self._status_label.text = "Fetching HRRR data"
                    self._pipeline = HRRRPipeline.execute(input_variable, input_datetime, num_timesteps=num_samples+1)
                    self._pipeline.add_done_callback(self._pipeline_callback)
                case _:
                    carb.log_error("Invalid data source option")
        except InputVariableError as e:
            self._status_label.text = str(e)
        except InputTimeRangeError as e:
            self._status_label.text = str(e)
        except Exception as e:
            carb.log_error(f"Something unexpected went wrong: {e}")
            self._pipeline = None
            self._status_label.text = "Pipeline Failed"

    def _pipeline_callback(self, future: concurrent.futures.Future):
        """Call back function to attach to the pipeline future object"""
        if future.exception():
            carb.log_error(f"Something unexpected went wrong: {future.exception()}")
            self._pipeline = None
            self._status_label.text = "Pipeline Failed"
        else:
            carb.log_info("Pipeline sucessful")
            self._status_label.text = ""

    @property
    def default_datetime(self) -> datetime:
        return datetime(2024,1,1,0,0,0)

    @property
    def source_labels(self) -> list[str]:
        return ["GFS", "ERA5", "FourCastNet", "HRRR"]

    @property
    def variables(self) -> list[str]:
        # These should be the keys used in the DFM extension
        return ["w10m", "t2m", "tp", "tcwv"]

    def reorder(self):
        """Example method to demonstrate image layer reordering

        Note
        ----
        This will cause a shader recompile to be queued which can take some time.
        """
        features_api = earth_core.get_state().get_features_api()
        image_features = features_api.get_image_features()
        # get current positions
        image_features_pos = [features_api.get_feature_pos(f) for f in image_features]
        # reverse order
        image_features_pos.reverse()
        # reorder with a feature->new_pos mapping
        features_api.reorder_features(dict(zip(image_features, image_features_pos)))

    def delete_layer(self):
        """Example method to demonstrate how to remove an image layer
        This will just delete the last most layer from the scene
        """
        features_api = earth_core.get_state().get_features_api()
        image_feature = features_api.get_image_features()[-1]
        features_api.remove_feature(image_feature)

    def build_window(self):
        """build the window for the Class"""
        self._editor_window = ui.Window("Data Federation Dialog", width=460, height=300)
        self._editor_window.setPosition(0, 0)
        date_style =  {"background_color": 0xFF33312F}

        carb.log_info("Building DFM UI")
        with self._editor_window.frame:
            with ui.VStack():
                ui.Label("DFM Pipelines")
                # Date time selections
                with ui.HStack():
                    ui.Label("Date-time (UTC)")
                    self._date_widget = DateWidget(model=DateModel(_datetime=self.default_datetime), style=date_style)
                    ui.Spacer(width=30)
                    self._time_widget = TimeWidget(model=TimeModel(_datetime=self.default_datetime))
                ui.Separator(height=10)
                with ui.HStack():
                    ui.Label("Timesteps (6 hr)")
                    self._num_samples = ui.SimpleIntModel(default_value=8, min=1, max=20)
                    self._num_samples_slider = ui.IntSlider(self._num_samples, width=184, min=1, max=20)
                # Variable selection
                ui.Separator(height=10)
                with ui.HStack():
                    ui.Label("Variable")
                    self._variable_combo = ui.ComboBox(0, *[VARIABLE_LABELS[v] for v in self.variables])
                # Data source selection
                ui.Separator(height=10)
                with ui.HStack():
                    ui.Label("Data Source")
                    self._source_combo = ui.ComboBox(0, *self.source_labels)
                # Run button
                self._fetch_button = ui.Button("Fetch Weather Data", clicked_fn=self.run)
                self._status_label = ui.Label("")

                ui.Separator(height=20)
                with ui.VStack():
                    ui.Label("ESRI")
                    with ui.HStack():
                        ui.Label("Processing Mode:")
                        self._esri_topo_combo = ui.ComboBox(0, *SUPPORTED_ESRI_PROCESSING_MODES)
                        ui.Button("Fetch Topography Map", clicked_fn=self.run_esri_pipeline)

                ## Other sample stuff for reference
                ui.Separator(height=10)
                with ui.HStack():
                    ui.Button("Reverse Layer Order", clicked_fn=self.reorder)
                    ui.Button("Delete Layer", clicked_fn=self.delete_layer)

        return self._editor_window

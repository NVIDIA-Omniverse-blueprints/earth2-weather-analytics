# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import concurrent
import carb
from datetime import datetime

from omni import ui
from omni.kit.window.filepicker.datetime import DateWidget, TimeWidget
from omni.kit.window.filepicker.datetime.calendar import DateModel
from omni.kit.window.filepicker.datetime.clock import TimeModel

from omni.earth_2_command_center.app.dfm.pipelines.aviation_weather import AviationWeatherPipeline
from omni.earth_2_command_center.app.dfm.pipelines.flight_route import FlightRoutePipeline
from omni.earth_2_command_center.app.dfm.pipelines.metar_stations import (
    MetarStationsPipeline,
    PirepPipeline,
    SigmetPipeline,
)
from omni.earth_2_command_center.app.dfm.utils.constants import VARIABLE_LABELS
from omni.earth_2_command_center.app.dfm.utils.exceptions import (
    InputVariableError,
    InputTimeRangeError,
)


# Aviation-specific variables
AVIATION_VARIABLES = ["wind_shear", "ellrod_ti", "icing_prob"]
AVIATION_SOURCES = ["GFS", "ERA5"]
FLIGHT_LEVEL_MIN = 100
FLIGHT_LEVEL_MAX = 450


class AviationWindow:
    def __init__(self):
        self._pipeline = None
        self._editor_window = None
        self._waypoints = []

        # Widget refs
        self._date_widget = None
        self._time_widget = None
        self._variable_combo = None
        self._source_combo = None
        self._fl_slider = None
        self._fl_model = None
        self._timesteps_model = None
        self._timesteps_slider = None
        self._status_label = None

        # METAR widgets
        self._metar_stations_field = None

        # Route widgets
        self._departure_field = None
        self._arrival_field = None
        self._route_date_widget = None
        self._route_time_widget = None
        self._speed_model = None
        self._waypoint_stack = None

    def shutdown(self):
        self._editor_window = None

    def hide(self):
        if self._editor_window:
            self._editor_window.visible = False

    def show(self):
        if self._editor_window:
            self._editor_window.visible = True

    @property
    def default_datetime(self) -> datetime:
        return datetime(2024, 1, 1, 0, 0, 0)

    def build_window(self):
        self._editor_window = ui.Window(
            "Aviation Weather Analytics", width=500, height=650
        )
        self._editor_window.setPosition(470, 0)
        date_style = {"background_color": 0xFF33312F}

        carb.log_info("Building Aviation UI")
        with self._editor_window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=4):

                    # === Section 1: Aviation Weather Layers ===
                    ui.Label("Aviation Weather Layers", style={"font_size": 16})
                    ui.Separator(height=5)

                    with ui.HStack():
                        ui.Label("Date-time (UTC)", width=120)
                        self._date_widget = DateWidget(
                            model=DateModel(_datetime=self.default_datetime),
                            style=date_style,
                        )
                        ui.Spacer(width=20)
                        self._time_widget = TimeWidget(
                            model=TimeModel(_datetime=self.default_datetime)
                        )

                    with ui.HStack():
                        ui.Label("Timesteps (6 hr)", width=120)
                        self._timesteps_model = ui.SimpleIntModel(
                            default_value=4, min=1, max=20
                        )
                        self._timesteps_slider = ui.IntSlider(
                            self._timesteps_model, width=200, min=1, max=20
                        )

                    with ui.HStack():
                        ui.Label("Variable", width=120)
                        self._variable_combo = ui.ComboBox(
                            0,
                            *[VARIABLE_LABELS[v] for v in AVIATION_VARIABLES],
                        )

                    with ui.HStack():
                        ui.Label("Flight Level", width=120)
                        self._fl_model = ui.SimpleIntModel(
                            default_value=300, min=FLIGHT_LEVEL_MIN, max=FLIGHT_LEVEL_MAX
                        )
                        self._fl_slider = ui.IntSlider(
                            self._fl_model,
                            width=200,
                            min=FLIGHT_LEVEL_MIN,
                            max=FLIGHT_LEVEL_MAX,
                        )
                        ui.Label("FL", width=30)

                    with ui.HStack():
                        ui.Label("Data Source", width=120)
                        self._source_combo = ui.ComboBox(0, *AVIATION_SOURCES)

                    ui.Button(
                        "Fetch Aviation Weather",
                        clicked_fn=self.run_aviation_weather,
                        height=30,
                    )

                    # === Section 2: METAR / Airport Data ===
                    ui.Separator(height=15)
                    ui.Label("METAR / Airport Data", style={"font_size": 16})
                    ui.Separator(height=5)

                    with ui.HStack():
                        ui.Label("Stations (ICAO)", width=120)
                        self._metar_stations_field = ui.StringField(width=300)
                        self._metar_stations_field.model.set_value("KJFK,KLAX,KORD,KATL")

                    with ui.HStack():
                        ui.Button("Load METAR", clicked_fn=self.run_metar, height=25)
                        ui.Button("Load PIREPs", clicked_fn=self.run_pirep, height=25)
                        ui.Button(
                            "Load SIGMETs", clicked_fn=self.run_sigmet, height=25
                        )
                        ui.Button(
                            "Load AIRMETs", clicked_fn=self.run_airmet, height=25
                        )

                    # === Section 3: Flight Route Planning ===
                    ui.Separator(height=15)
                    ui.Label("Flight Route Planning", style={"font_size": 16})
                    ui.Separator(height=5)

                    with ui.HStack():
                        ui.Label("Departure", width=120)
                        self._departure_field = ui.StringField(width=100)
                        self._departure_field.model.set_value("KJFK")
                        ui.Spacer(width=20)
                        ui.Label("Arrival", width=60)
                        self._arrival_field = ui.StringField(width=100)
                        self._arrival_field.model.set_value("KLAX")

                    with ui.HStack():
                        ui.Label("Departure Time", width=120)
                        self._route_date_widget = DateWidget(
                            model=DateModel(_datetime=self.default_datetime),
                            style=date_style,
                        )
                        ui.Spacer(width=20)
                        self._route_time_widget = TimeWidget(
                            model=TimeModel(_datetime=self.default_datetime)
                        )

                    with ui.HStack():
                        ui.Label("Ground Speed", width=120)
                        self._speed_model = ui.SimpleFloatModel(default_value=450.0)
                        ui.FloatField(self._speed_model, width=100)
                        ui.Label("kts", width=30)

                    ui.Separator(height=5)
                    ui.Label("Waypoints (lat, lon, altitude_ft):")
                    self._waypoint_stack = ui.VStack()
                    self._waypoint_models = []
                    # Add initial waypoints for KJFK -> KLAX
                    self._add_default_waypoints()

                    with ui.HStack():
                        ui.Button(
                            "Add Waypoint", clicked_fn=self._add_waypoint, height=25
                        )
                        ui.Button(
                            "Clear Waypoints",
                            clicked_fn=self._clear_waypoints,
                            height=25,
                        )

                    ui.Button(
                        "Analyze Route",
                        clicked_fn=self.run_route_analysis,
                        height=30,
                    )

                    # === Status ===
                    ui.Separator(height=15)
                    self._status_label = ui.Label("")

        return self._editor_window

    def _add_default_waypoints(self):
        # KJFK to KLAX example waypoints
        defaults = [
            (40.64, -73.78, 35000, "KJFK"),
            (39.50, -80.00, 37000, ""),
            (37.00, -95.00, 37000, ""),
            (35.00, -110.00, 37000, ""),
            (33.94, -118.41, 35000, "KLAX"),
        ]
        for lat, lon, alt, name in defaults:
            self._add_waypoint(lat, lon, alt, name)

    def _add_waypoint(self, lat=0.0, lon=0.0, alt=35000.0, name=""):
        lat_model = ui.SimpleFloatModel(default_value=lat)
        lon_model = ui.SimpleFloatModel(default_value=lon)
        alt_model = ui.SimpleFloatModel(default_value=alt)
        name_model = ui.SimpleStringModel(default_value=name)

        with self._waypoint_stack:
            with ui.HStack(height=20):
                ui.Label(f"WP{len(self._waypoint_models) + 1}", width=35)
                ui.FloatField(lat_model, width=80)
                ui.FloatField(lon_model, width=80)
                ui.FloatField(alt_model, width=80)
                ui.StringField(name_model, width=80)

        self._waypoint_models.append((lat_model, lon_model, alt_model, name_model))

    def _clear_waypoints(self):
        self._waypoint_models.clear()
        # Rebuild empty stack
        self._waypoint_stack.clear()

    def _get_waypoints(self) -> list:
        waypoints = []
        for lat_m, lon_m, alt_m, name_m in self._waypoint_models:
            wp = {
                "lat": lat_m.as_float,
                "lon": lon_m.as_float,
                "altitude_ft": alt_m.as_float,
            }
            name = name_m.as_string if hasattr(name_m, "as_string") else name_m.get_value_as_string()
            if name:
                wp["name"] = name
            waypoints.append(wp)
        return waypoints

    def _pipeline_callback(self, future: concurrent.futures.Future):
        if future.exception():
            carb.log_error(f"Aviation pipeline error: {future.exception()}")
            self._pipeline = None
            self._status_label.text = "Pipeline Failed"
        else:
            carb.log_info("Aviation pipeline successful")
            self._pipeline = None
            self._status_label.text = "Complete"

    def _check_pipeline_running(self) -> bool:
        if self._pipeline is not None and not self._pipeline.done():
            carb.log_error("Pipeline already running!")
            self._status_label.text = "Pipeline Running"
            return True
        return False

    def run_aviation_weather(self):
        if self._check_pipeline_running():
            return

        input_datetime = datetime(
            self._date_widget.model.year,
            self._date_widget.model.month,
            self._date_widget.model.day,
            self._time_widget.model.hour,
            self._time_widget.model.minute,
            self._time_widget.model.second,
        )
        variable = AVIATION_VARIABLES[
            self._variable_combo.model.get_item_value_model().get_value_as_int()
        ]
        source = AVIATION_SOURCES[
            self._source_combo.model.get_item_value_model().get_value_as_int()
        ].lower()
        num_timesteps = self._timesteps_model.as_int

        try:
            self._status_label.text = f"Fetching {VARIABLE_LABELS[variable]}..."
            self._pipeline = AviationWeatherPipeline.execute(
                variable,
                input_datetime,
                num_timesteps=num_timesteps,
                provider=source,
            )
            self._pipeline.add_done_callback(self._pipeline_callback)
        except (InputVariableError, InputTimeRangeError) as e:
            self._status_label.text = str(e)
        except Exception as e:
            carb.log_error(f"Aviation weather error: {e}")
            self._pipeline = None
            self._status_label.text = "Pipeline Failed"

    def run_metar(self):
        if self._check_pipeline_running():
            return

        stations_str = self._metar_stations_field.model.get_value_as_string().strip()
        stations = (
            [s.strip() for s in stations_str.split(",") if s.strip()]
            if stations_str
            else None
        )

        try:
            self._status_label.text = "Loading METAR data..."
            self._pipeline = MetarStationsPipeline.execute(stations=stations)
            self._pipeline.add_done_callback(self._pipeline_callback)
        except Exception as e:
            carb.log_error(f"METAR error: {e}")
            self._pipeline = None
            self._status_label.text = "METAR Failed"

    def run_pirep(self):
        if self._check_pipeline_running():
            return
        try:
            self._status_label.text = "Loading PIREPs..."
            self._pipeline = PirepPipeline.execute()
            self._pipeline.add_done_callback(self._pipeline_callback)
        except Exception as e:
            carb.log_error(f"PIREP error: {e}")
            self._pipeline = None
            self._status_label.text = "PIREP Failed"

    def run_sigmet(self):
        if self._check_pipeline_running():
            return
        try:
            self._status_label.text = "Loading SIGMETs..."
            self._pipeline = SigmetPipeline.execute(hazard_type="sigmet")
            self._pipeline.add_done_callback(self._pipeline_callback)
        except Exception as e:
            carb.log_error(f"SIGMET error: {e}")
            self._pipeline = None
            self._status_label.text = "SIGMET Failed"

    def run_airmet(self):
        if self._check_pipeline_running():
            return
        try:
            self._status_label.text = "Loading AIRMETs..."
            self._pipeline = SigmetPipeline.execute(hazard_type="airmet")
            self._pipeline.add_done_callback(self._pipeline_callback)
        except Exception as e:
            carb.log_error(f"AIRMET error: {e}")
            self._pipeline = None
            self._status_label.text = "AIRMET Failed"

    def run_route_analysis(self):
        if self._check_pipeline_running():
            return

        waypoints = self._get_waypoints()
        if len(waypoints) < 2:
            self._status_label.text = "Need at least 2 waypoints"
            return

        dep_time = datetime(
            self._route_date_widget.model.year,
            self._route_date_widget.model.month,
            self._route_date_widget.model.day,
            self._route_time_widget.model.hour,
            self._route_time_widget.model.minute,
            self._route_time_widget.model.second,
        )
        speed = self._speed_model.as_float

        try:
            self._status_label.text = "Analyzing flight route..."
            self._pipeline = FlightRoutePipeline.execute(
                waypoints=waypoints,
                departure_time=dep_time.isoformat(),
                dateobj=dep_time,
                ground_speed_kts=speed,
            )
            self._pipeline.add_done_callback(self._pipeline_callback)
        except Exception as e:
            carb.log_error(f"Route analysis error: {e}")
            self._pipeline = None
            self._status_label.text = "Route Analysis Failed"

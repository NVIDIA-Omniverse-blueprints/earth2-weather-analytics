# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import time
import asyncio
from typing import Callable, Dict, Optional, Union
from functools import partial

import carb
from carb.settings import get_settings
from pxr import Gf

import omni.kit.app
from omni import ui
import omni.usd as ou

import omni.kit.actions.core
import omni.kit.hotkeys.core
from omni.kit.menu.utils import add_menu_items, remove_menu_items, MenuItemDescription

from omni.kit.viewport.utility import get_active_viewport_camera_path
from omni.kit.viewport.utility.camera_state import ViewportCameraState

import omni.earth_2_command_center.app.core as earth_core
import omni.earth_2_command_center.app.core.features_api as FeaturesApi

from .reference_manager import ReferenceManager
from .timeline.minibar import TimelineMinibar
from .timeline.datebar import DatePickerWidget
from .style import (
    FEATURE_PANEL,
    NAVIGATION_PANEL,
    INFO_PANEL,
    INFO_TEXT
)

ZOOM_STEP: int = 3000
FEATURE_EXCLUDE = [] # ["unnamed"]

# BLUE MARBLE [Africa/Antarctica]
CAM_DEFAULTS = {
        'xformOp:translate': Gf.Vec3d(14508.205314825205, 12510.310453034006, 5827.069287601547),
        'xformOp:rotateXYZ': Gf.Vec3d(73.0817, -2.2263883e-14, 130.77094),
}

# INITIAL CAMERA
# CAM_DEFAULTS = {
#     'xformOp:translate': Gf.Vec3d(-5157.699457971259, 13767.437069140029, 9384.427792726257),
#     'xformOp:rotateXYZ': Gf.Vec3f(57.58460998535156, 0.0, -159.5652313232422),
#     'xformOp:scale': Gf.Vec3f(1.0, 1.0, 1.0)
# }

class GlobeUI:
    def __init__(self, ext_id: str, viewport_window):


        self.__window = viewport_window
        self._ext_id = ext_id
        ext_name = omni.ext.get_extension_name(self._ext_id)

        self.__visible = True
        self.__ctx = ou.get_context()
        self.__frame: Optional[ui.Frame] = viewport_window.get_frame(ext_id)
        self.__features_api = earth_core.get_state().get_features_api()
        self.__features_api_subscription = self.__features_api.get_event_stream().create_subscription_to_pop(self._on_feature_change)

        self._feature_frame = None
        self._timeline_frame = None
        self._navigation_frame = None
        #self._info_frame = None

        #self.__cursor: CustomCursor = CustomCursor()

        settings = get_settings()
        self.__zoom_min = settings.get_as_int(f"/exts/{ext_name}/zoom_min")
        self.__zoom_max = settings.get_as_int(f"/exts/{ext_name}/zoom_max")

        self.__camera_path = get_active_viewport_camera_path()
        self.__on_home_clicked(instant=True)

        # Set UI reference for access
        ReferenceManager().globe_ui = self

        # get the extension manager
        ext_manager = omni.kit.app.get_app_interface().get_extension_manager()
        feature_properties_ext_name = 'omni.earth_2_command_center.app.window.feature_properties'
        # register callbacks for when feature properties window is enabled/disabled
        # if the extension is already loaded, the callback is triggered immediately
        self._feature_properties_hook = ext_manager.subscribe_to_extension_enable(
                self.__on_feature_properties_status_change,
                self.__on_feature_properties_status_change,
                feature_properties_ext_name)
        test_sequence_ext_name = 'omni.earth_2_command_center.app.window.test_sequence'
        self._test_sequence_hook = ext_manager.subscribe_to_extension_enable(
                self.__on_test_sequence_status_change,
                self.__on_test_sequence_status_change,
                test_sequence_ext_name)

        def toggle_visibility():
            self.visible = not self.visible

            from omni.kit.mainwindow import get_main_window
            settings_path = "/app/mainMenuBar/visible"
            value_when_visible = settings.get_as_bool(settings_path)
            main_window = get_main_window()
            main_window.get_main_menu_bar().visible = value_when_visible if self.visible else False

        action_registry = omni.kit.actions.core.acquire_action_registry()
        toggle_ui_action = action_registry.register_action(self._ext_id, 'toggle_ui', toggle_visibility, 'Toggle Globe UI', 'Toggle visibility of Globe UI elements')
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.register_hotkey(self._ext_id, 'F7', self._ext_id, 'toggle_ui')

        self._menu_entry = MenuItemDescription("Toggle UI Elements (F7)",
                    ticked=True,
                    ticked_value=self.visible,
                    onclick_action=(self._ext_id, 'toggle_ui'))
        add_menu_items([self._menu_entry], name="View")

        self.__frame.set_build_fn(self.__build_ui)

    #@property
    #def cursor(self) -> CustomCursor:
    #    return self.__cursor

    @property
    def visible(self) -> bool:
        return self.__visible

    @visible.setter
    def visible(self, v):
        if v != self.__visible:
            self.__visible = v
            self.__frame.rebuild()

    def unload(self):
        if self.__frame is not None:
            self.__frame = None

        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.deregister_all_hotkeys_for_extension(self._ext_id)
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.deregister_all_actions_for_extension(self._ext_id)

        remove_menu_items([self._menu_entry], name='View')

    def _on_feature_change(self, event):
        needs_rebuild = False
        timeline_needs_rebuild = False

        if event.type in [\
                FeaturesApi.FeatureChange.FEATURE_ADD['id'],\
                FeaturesApi.FeatureChange.FEATURE_REMOVE['id'],\
                FeaturesApi.FeatureChange.FEATURE_CLEAR['id'],
                FeaturesApi.FeatureChange.FEATURE_REORDER['id'],
                          ]:
            needs_rebuild = True
            timeline_needs_rebuild = True

        elif event.type == FeaturesApi.FeatureChange.PROPERTY_CHANGE['id']:
            # handle only name, active, and colormap changes to
            # avoid excessive rebuilding
            name = event.payload['property']
            if name in ['name', 'active', 'colormap']:
                needs_rebuild = True

            if name in ['active', 'time_coverage']:
                timeline_needs_rebuild = True

        if needs_rebuild:
            if self._feature_frame:
                self._feature_frame.rebuild()
        if timeline_needs_rebuild:
            if self._timeline_frame:
                self._timeline_frame.rebuild()

    def __build_ui(self):
        """
            Builds the core UI Elements
        """
        if not self.__frame:
            return

        with self.__frame:
            with ui.ZStack(width=ui.Percent(100), height=ui.Percent(100)):
                if self.visible:
                    self._feature_frame = ui.Frame(spacing=0)  # Top Right
                    self._timeline_frame = ui.Frame(spacing=0) # Bottom Middle
                    self._navigation_frame = ui.Frame(spacing=0)  # Top Left
                    #self._info_frame = ui.Frame(spacing=0) # Bottom

                    # use settings to determine the visibility of these UI elements
                    ext_name = omni.ext.get_extension_name(self._ext_id)
                    settings = get_settings()
                    ui_elements_settings = [
                            (f"/exts/{ext_name}/feature/visible",    True, self._feature_frame),
                            (f"/exts/{ext_name}/timeline/visible",   True, self._timeline_frame),
                            (f"/exts/{ext_name}/navigation/visible", True, self._navigation_frame)]
                    for settings_path, default, frame in ui_elements_settings:
                        settings.set_default_bool(settings_path, default)
                        frame.visible = settings.get_as_bool(settings_path)

                    self._feature_frame.set_build_fn(self.__build_feature_ui)
                    self._timeline_frame.set_build_fn(self.__build_timeline_ui)
                    self._navigation_frame.set_build_fn(self.__build_navigation_ui)
                    #self._info_frame.set_build_fn(self.__build_info_ui)

        self.__frame.set_computed_content_size_changed_fn(self.__on_frame_size_changed)

    ############################################
    # UI
    ############################################
    def __build_navigation_ui(self):
        def build_button_group(name:str, clicked_fn: Callable, tooltip = ''):
            with ui.HStack(height=30):
                ui.Spacer()
                ui.Button("", name=name, width=0, height=0, image_width=30, image_height=30, clicked_fn=clicked_fn, tooltip = tooltip)
                ui.Spacer()

        with ui.HStack(name="navigation_stack", spacing=0, style=NAVIGATION_PANEL):
            ui.Spacer(width=30)
            # Panel
            with ui.VStack(spacing=0, width=50, height=0):
                ui.Spacer(height=30)
                with ui.ZStack(content_clipping=1, opaque_for_mouse_events=True):
                    ui.Rectangle(name="background")
                    with ui.VStack(spacing=10):
                        ui.Spacer()
                        build_button_group("nav_zoom_in", lambda: self.__on_zoom_clicked(True), tooltip='Zoom In')
                        build_button_group("nav_zoom_out", lambda: self.__on_zoom_clicked(False), tooltip='Zoom Out')
                        build_button_group("nav_home", self.__on_home_clicked, tooltip='Reset View')

                        #build_button_group("refresh", self.__on_refresh_clicked, tooltip='Recompile Shader')
                        #if self._is_feature_properties_enabled():
                        #    build_button_group("feature_properties", self.__on_feature_properties_clicked, tooltip='Open Feature Properties Window')

                        ## add button to add features from json file
                        ## TODO: seems tedious to get an action from a known extension without knowing its version
                        #action_registry = omni.kit.actions.core.acquire_action_registry()
                        #for action in action_registry.get_all_actions():
                        #    if action.id == 'e2cc.add_from_file':
                        #        def execute_action(action):
                        #            action.execute()
                        #        if action:
                        #            build_button_group("add", partial(execute_action, action), tooltip='Add from MetaData JSON')
                        #        else:
                        #            carb.log_error('action not found')
                        ui.Spacer()

    def _is_feature_properties_enabled(self):
        # get the extension manager
        ext_manager = omni.kit.app.get_app_interface().get_extension_manager()
        feature_properties_ext_name = 'omni.earth_2_command_center.app.window.feature_properties'
        return ext_manager.is_extension_enabled(feature_properties_ext_name)

    def __on_refresh_clicked(self):
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action = action_registry.get_action(self._ext_id, 'refresh')
        if action:
            action.execute()
        else:
            carb.log_error('refresh action not found in registry')

    def __on_feature_properties_clicked(self):
        if self._is_feature_properties_enabled():
            from omni.earth_2_command_center.app.window.feature_properties import get_instance
            ui.Workspace.show_window(get_instance().WINDOW_NAME)

    def __on_feature_properties_status_change(self, ext_id:str):
        if self._navigation_frame:
            self._navigation_frame.rebuild()

    def __on_test_sequence_status_change(self, ext_id:str):
        if self._navigation_frame:
            self._navigation_frame.rebuild()

    def __build_feature_ui(self):
        import omni.earth_2_command_center.app.shading as shading
        shader_library = shading.get_shader_library()

        def build_button_group(feature, button_name: str):
            with ui.VStack(height=0, spacing=0):
                label_width = 200
                with ui.HStack(name="feature_row", height=30, spacing=12):
                    btn = ui.Button(
                        "",
                        name=button_name,
                        tooltip='Toggle Visibility',
                        width=0,
                        height=0,
                        image_width=30,
                        image_height=30,
                        checked = feature.active
                    )
                    ui.Label(feature.name, width=label_width, word_wrap=True)

                color_stack = None
                img = None
                if feature.feature_type == "Image" and feature.colormap is not None:
                    color_map_path = shader_library.get_colormap_path(feature.colormap)
                    map_height = 8 if feature.active else 0
                    color_stack = ui.HStack(height=map_height)
                    with color_stack:
                        ui.Spacer()
                        img = ui.Image(color_map_path, width=label_width, fill_policy=ui.FillPolicy.STRETCH)

                btn.set_clicked_fn(lambda b=btn, f=feature, i=img: self.__on_feature_clicked(b, f, i))

        with ui.HStack(name="feature_stack", spacing=0, style=FEATURE_PANEL):
            ui.Spacer()
            # Panel
            with ui.VStack(spacing=10, width=266, height=0):
                ui.Spacer(height=20)
                with ui.ZStack(height=0, content_clipping=1, opaque_for_mouse_events=True):
                    with ui.VStack(spacing=0):
                        with ui.ZStack(direction=ui.Direction.FRONT_TO_BACK):
                            with ui.ZStack(height=10):
                                ui.Rectangle(name="foreground")
                                ui.Line()
                            ui.Rectangle(name="background")
                    with ui.VStack(name="features", spacing=0):
                        ui.Spacer(height=8)

                        def section_start(heading):
                            with ui.HStack(spacing=4):
                                ui.Label(heading, width=0)
                                ui.Line()
                        def section_fill(features):
                            for f in features:
                                if f.name not in FEATURE_EXCLUDE:
                                    build_button_group(f, "visible_toggle")
                                    ui.Spacer(height=4)
                        def section_end():
                            ui.Spacer(height=8)

                        # Image Features
                        section_start('Image Layers')
                        section_fill(self.__features_api.get_by_type(FeaturesApi.Image))
                        section_end()

                        # Misc Features (not Images, not Lights)
                        section_start('Misc')
                        section_fill(self.__features_api.get_by_types([FeaturesApi.Image, FeaturesApi.Light], invert=True))
                        section_end()

                        # Light Features
                        section_start('Lights')
                        section_fill(self.__features_api.get_by_type(FeaturesApi.Light))
                        section_end()

                ui.Spacer()
            ui.Spacer(width=30)

    def __build_timeline_ui(self):
        with ui.VStack(name="timeline_stack", spacing=0, style={}):
            ui.Spacer()
            # Panel
            with ui.VStack(spacing=6, height=140):
                ui.Spacer()
                with ui.HStack(spacing=0):
                    ui.Spacer()
                    with ui.ZStack(spacing=0, width=500, content_clipping=1, opaque_for_mouse_events=True):
                        self._minibar = TimelineMinibar()
                    ui.Spacer()
                ui.Spacer(height=30)

    ############################################
    # CALLBACKS
    ############################################
    async def __interpolate_position(
            self,
            camera_state: ViewportCameraState,
            start: Gf.Vec3d,
            end: Gf.Vec3d,
            seconds_override: Optional[float] = None
    ):
            def ease_in_out_cubic(t):
                return 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2

            def get_interp_time(start_pt: Gf.Vec3d):
                range = self.__zoom_max - self.__zoom_min
                min_dist = start_pt.GetLength() - self.__zoom_min
                return min_dist / range

            if seconds_override is not None:
                n_seconds = seconds_override
            else:
                n_seconds = get_interp_time(start) * 1.5
                n_seconds = n_seconds if n_seconds > 1.5 else 1.5

            start_time = time.time()
            while time.time() - start_time < n_seconds:
                current_time = time.time() - start_time
                t = current_time / n_seconds  # normalize 0-1
                i_val = start + (end - start) * ease_in_out_cubic(t)
                camera_state.set_position_world(i_val, True)
                camera_state.set_target_world(Gf.Vec3d(0,0,0), True)
                await omni.kit.app.get_app().next_update_async()

    def __on_zoom_clicked(self, zoom_in: bool):
        camera_state = ViewportCameraState(self.__camera_path)

        step_size = -ZOOM_STEP if zoom_in else ZOOM_STEP
        # compute camera position and new position along forward vector
        # Limit the position if calculated is not between the min/max.
        start_pos = camera_state.position_world

        new_pos = start_pos + (start_pos.GetNormalized() * step_size)
        new_dist = new_pos.GetLength()
        if not self.__zoom_max > new_dist > self.__zoom_min:
            return

        asyncio.ensure_future(self.__interpolate_position(camera_state, start_pos, new_pos))

    def on_scroll(self, input_value):
        camera_state = ViewportCameraState(self.__camera_path)
        # compute camera position and new position along forward vector
        # Limit the position if calculated is not between the min/max.
        start_pos = camera_state.position_world

        new_pos = start_pos + (start_pos.GetNormalized() * -input_value * ZOOM_STEP * 0.5)
        new_dist = new_pos.GetLength()
        if not self.__zoom_max > new_dist > self.__zoom_min:
            return

        camera_state.set_position_world(new_pos, True)
        camera_state.set_target_world(Gf.Vec3d(0,0,0), True)
        # asyncio.ensure_future(self.__interpolate_position(camera_state, start_pos, new_pos))#, seconds_override=1.5))


    def __on_home_clicked(self, instant=False):
        camera_state = ViewportCameraState(self.__camera_path)
        start_pos = camera_state.position_world
        end_pos = CAM_DEFAULTS["xformOp:translate"]

        if instant:
            camera_state.set_position_world(end_pos, True)
            camera_state.set_target_world(Gf.Vec3d(0,0,0), True)
            return

        asyncio.ensure_future(self.__interpolate_position(camera_state, start_pos, end_pos))

    def __on_feature_clicked(self, button: ui.Button, feature, image: Optional[ui.Image]) -> None:
        async def animate_stack(img: ui.Image, visible: bool):
            iteration = range(16) if visible else reversed(range(16))
            for i in iteration:
                await omni.kit.app.get_app().next_update_async()
                img.height = ui.Pixel(i)

        button.checked = feature.active = not button.checked

        if image:
            asyncio.ensure_future(animate_stack(image, button.checked))

    def __on_frame_size_changed(self) -> None:
        """
            Callback for the ViewportWindow Frame size change
        """
        if not self.__frame:
            return

        width, height = self.__frame.computed_content_width, self.__frame.computed_content_height

        # Do whatever show hide here based on size
        # Values determined by design
        # self._navigation_stack.visible = height > 240 and width >= 640  # example

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
from typing import Optional
__all__ = ['FeatureExtension', 'get_instance']

from .feature_properties_window import FeaturePropertiesWindow

from functools import partial

import omni.kit.app
import omni.ext
import omni.ui as ui

import carb.events
import carb.settings
import carb.tokens

from omni.kit.menu.utils import add_menu_items, MenuItemDescription

SETTING_SHOW_STARTUP = "/exts/omni.earth_2_command_center.app.window.feature_window/showStartup"

instance: Optional['FeatureExtension'] = None


def get_instance():
    global instance
    return instance

class FeatureExtension(omni.ext.IExt):
    WINDOW_NAME = "Feature Properties"
    MENU_PATH = f"Window/{WINDOW_NAME}"

    def on_startup(self, ext_id):
        self._ext_id = ext_id

        global instance
        instance = self

        self._window = None
        ui.Workspace.set_show_window_fn(
                FeatureExtension.WINDOW_NAME,
                partial(self.show_window, FeatureExtension.MENU_PATH))

        show_startup = carb.settings.get_settings().get(SETTING_SHOW_STARTUP)

        ##add_menu_items([
        ##    MenuItemDescription(FeatureExtension.WINDOW_NAME,
        ##        onclick_fn=self.show_window,
        ##        ticked = show_startup)
        ##    ], 'Window')
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            self._menu = editor_menu.add_item(FeatureExtension.MENU_PATH, self.show_window, toggle=True, value=show_startup)

        self._feature_type_callbacks = {}

    def show_window(self, menu_path:str, visible:bool):
        if self._window is None:
            self._window = FeaturePropertiesWindow(FeatureExtension.WINDOW_NAME, width=600, height=400)
            self._window.set_visibility_changed_fn(self._visiblity_changed_fn)
            self._window.set_feature_type_callbacks(self._feature_type_callbacks)

        if visible:
            self._window.visible = True
        elif self._window:
            self._window.visible = False

    def _set_menu(self, checked: bool):
        """Set the menu to create this window on and off"""
        editor_menu = omni.kit.ui.get_editor_menu()
        if editor_menu:
            editor_menu.set_value(FeatureExtension.MENU_PATH, checked)

    def _visiblity_changed_fn(self, visible):
        self._set_menu(visible)

    def register_feature_type_add_callback(self, name, call_fn):
        self._feature_type_callbacks[name] = call_fn
        if self._window is not None:
            self._window.set_feature_type_callbacks(self._feature_type_callbacks)

    def unregister_feature_type_add_callback(self, name):
        del self._feature_type_callbacks[name]
        if self._window is not None:
            self._window.set_feature_type_callbacks(self._feature_type_callbacks)

    def get_feature_type_add_callbacks(self):
        return self._feature_type_callbacks.copy()

    # XXX: excluded from test coverage as fastShutdown seems to be on during testing
    # and thus it will never on_shutdown
    def on_shutdown(self): # pragma: no cover
        global instance
        instance = None
        if self._window:
            ui.Workspace.set_show_window_fn(FeatureExtension.WINDOW_NAME, None)
            self._window.destroy()
            self._window = None

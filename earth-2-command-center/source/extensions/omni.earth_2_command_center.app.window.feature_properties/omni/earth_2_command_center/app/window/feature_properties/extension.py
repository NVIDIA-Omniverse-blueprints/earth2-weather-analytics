from __future__ import annotations
from typing import Optional
__all__ = ['FeatureExtension', 'get_instance']

from .feature_properties_window import FeaturePropertiesWindow

from functools import partial

import omni.kit.app
import omni.ext
import omni.ui as ui
import omni.kit.menu.utils

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

        def is_visible():
            return self._window is not None and self._window.visible

        # register actions
        action_registry = omni.kit.actions.core.get_action_registry()
        action_registry.register_action(
            ext_id, "show_window", lambda:self.show_window)
        menu_dict = omni.kit.menu.utils.build_submenu_dict([
            MenuItemDescription(name=FeatureExtension.MENU_PATH,
                                onclick_action=(ext_id, "show_window"),
                                ticked_fn=is_visible, ticked_value=show_startup)])
        for group in menu_dict:
            omni.kit.menu.utils.add_menu_items(menu_dict[group], group)

        self._feature_type_callbacks = {}

    def show_window(self, menu=None, visible=None):
        if self._window is None:
            self._window = FeaturePropertiesWindow(FeatureExtension.WINDOW_NAME, width=600, height=400)
            self._window.set_feature_type_callbacks(self._feature_type_callbacks)
        else:
            self._window.visible = visible if visible is not None else not self._window.visible

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

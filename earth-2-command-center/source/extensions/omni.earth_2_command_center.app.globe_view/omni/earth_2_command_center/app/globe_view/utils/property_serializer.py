__all__ = [ 'PropertySerialiser' ]

import json
import copy
from pathlib import Path
import tempfile

import carb
from omni.kit.menu.utils import add_menu_items, remove_menu_items, MenuItemDescription
from omni.kit.actions.core import get_action_registry

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.features import *
from omni.kit.window.filepicker import FilePickerDialog

class PropertySerialiser():
    def __init__(self, extension_id):
        self._ext_id = extension_id
        self._start_directory = tempfile.gettempdir()
        self._start_filename = 'file.json'
        self._properties_to_save = {
                Feature: [ 'active' ],
                Image: [
                        # not in main branch yet
                        #'loop',
                        'colormap', 'remapping' ],
                Light: [],
                Sun: [ 'diurnal_motion', 'seasonal_motion', 'longitude', 'latitude', 'follow_camera' ]}
        self._registered_actions = []
        self._registered_menus = []
        self._setup_actions()
        self._setup_menus()

    def _setup_actions(self):
        if self._ext_id is None:
            raise RuntimeError('_setup_actions called before setup')
        action_registry = get_action_registry()
        actions_tag = "PropertySerialiser"

        if "save_properties" not in self._registered_actions:
            action_registry.register_action(
                self._ext_id,
                "save_properties",
                lambda: self.save_remapping_dialog(),
                display_name="Save Properties",
                description="Saves E2CC Feature Properties to a JSON file",
                tag=actions_tag,
            )
            self._registered_actions.append("save_properties")
        if "load_properties" not in self._registered_actions:
            action_registry.register_action(
                self._ext_id,
                "load_properties",
                lambda: self.load_remapping_dialog(),
                display_name="Load Properties",
                description="Loads E2CC Feature Properties from a JSON file",
                tag=actions_tag,
            )
            self._registered_actions.append("load_properties")

    def _deregister_actions(self):
        if self._ext_id is not None:
            action_registry = get_action_registry()
            for action_name in self._registered_actions:
                action_registry.deregister_action(self._ext_id, action_name)
            self._registered_actions = []

    def _setup_menus(self):
        if self._ext_id is None:
            raise RuntimeError('_setup_menus called before setup')
        if self._registered_menus:
            carb.log_warn('Menus already setup')
            return

        menu_entry = [
                MenuItemDescription(name='Configuration', sub_menu=[
                    MenuItemDescription(
                        name='Export',
                        onclick_action=(self._ext_id, "save_properties"),
                        )
                    ,
                    MenuItemDescription(
                        name='Import',
                        onclick_action=(self._ext_id, "load_properties"),
                        )
                    ])]
        add_menu_items(menu_entry, name="Utilities")
        self._registered_menus = menu_entry

    def _remove_menus(self):
        if self._registered_menus:
            remove_menu_items(self._registered_menus, name="Utilities")
            self._registered_menus = []

    def _open_filepicker_dialog(self, title, button_label, callback, start_directory=None, start_filename=None):
        def on_click(dialog, filename, dirname):
            self._start_directory = dirname
            self._start_filename = filename
            callback(Path(dirname)/Path(filename))
            dialog.hide()

        dialog = FilePickerDialog(
                title,
                apply_button_label = button_label,
                show_detail_view = False,
                enable_checkpoints = False,
                current_directory = start_directory,
                current_filename = start_filename,
                click_apply_handler = lambda filename, dirname: on_click(dialog, Path(filename), Path(dirname)))

    def save_remapping_dialog(self):
        self._open_filepicker_dialog('Export Configuration', 'Export', self._save_remapping,
                              start_directory = self._start_directory, start_filename = self._start_filename)
    def load_remapping_dialog(self):
        self._open_filepicker_dialog('Import Configuration', 'Import', self._load_remapping,
                              start_directory = self._start_directory, start_filename = self._start_filename)

    def _save_remapping(self, file_path):
        features_api = get_state().get_features_api()

        to_save = {}
        features = features_api.get_features()
        for f in features:
            if f.name in to_save:
                carb.log_warn(f'Features with duplicate names present? {f.name}')
                continue
            cur = {}
            for feature_type, property_list in self._properties_to_save.items():
                if not isinstance(f, feature_type):
                    continue
                for p in property_list:
                    cur[p] = getattr(f, p)
            to_save[f.name] = copy.copy(cur)

        with open(file_path, 'w') as file:
            json.dump(to_save, file, indent=2)

    def _load_remapping(self, file_path):
        to_load = []
        with open(file_path, 'r') as file:
            to_load = json.load(file)

        features_api = get_state().get_features_api()
        for f in features_api.get_features():
            target = to_load.get(f.name, None)
            if not target:
                continue
            #carb.log_warn(f'Restoring settings for \'{f.name}\'')
            for k,v in target.items():
                if hasattr(f, k):
                    setattr(f, k, v)
                else:
                    carb.log_warn(f'Skipping property {k} as not present on target {f.name}')

    def __del__(self):
        self._remove_menus()
        self._deregister_actions()


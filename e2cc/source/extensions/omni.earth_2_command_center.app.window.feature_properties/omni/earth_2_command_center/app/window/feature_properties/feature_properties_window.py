# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core import features_api as features_api_module
from omni.earth_2_command_center.app.shading import get_shader_library

from .style import ICON_PATHS, STYLES
from .colormap_dialog import ColormapDialog

from omni.kit.window.popup_dialog import InputDialog, MessageDialog

import omni.ui as ui
import omni.kit.ui
import carb.settings

from functools import partial

# NOTE: The models don't subscribe to events but they get informed by view
# through 'handle_event'. This minimizes the number of subscriptions and makes
# models more lightweight
class FeaturePropertyModel(ui.AbstractValueModel):
    def __init__(self, feature, property_name:str, nested_property_name:str = None, no_edit_changes:bool = False):
        super().__init__()
        self._feature = feature
        self._property_name = property_name
        self._nested_property_name = nested_property_name
        state = get_state()
        self._features_api = state.get_features_api()

        self._no_edit_changes = no_edit_changes
        self._disable_change = False

    def begin_edit(self):
        if self._no_edit_changes:
            self._disable_change = True
        super().begin_edit()

    def end_edit(self):
        if self._no_edit_changes:
            self._disable_change = False
            self.set_value(self._tmp_value)
        super().end_edit()

    def destroy(self):
        self._feature = None

    def __del__(self):
        self.destroy()

    def handle_event(self, event):
        return self._on_feature_change(event)

    def _on_feature_change(self, event):
        feature_id = event.sender
        if self._feature.id != feature_id:
            return False
        # check if it's a property change
        change = event.payload['change']
        if change['id'] == features_api_module.FeatureChange.PROPERTY_CHANGE['id']:
            # check if it's our property
            property_name = event.payload['property']
            if property_name == self._property_name:
                self.set_value(self._get())
                return True
        return False

    def _get(self):
        if self._nested_property_name is not None:
            #return self._to_native_type(getattr(self._feature, self._property_name).get(self._nested_property_name))
            return getattr(self._feature, self._property_name).get(self._nested_property_name)
        else:
            return getattr(self._feature, self._property_name)

    def _set(self, value):
        # convert to native type
        value = self._to_native_type(value)
        if self._nested_property_name is not None:
            p = getattr(self._feature, self._property_name)
            p[self._nested_property_name] = value
            setattr(self._feature, self._property_name, p)
        else:
            setattr(self._feature, self._property_name, value)

    # get type of feature property
    def _get_native_type(self):
        if self._nested_property_name is not None:
            p = getattr(self._feature, self._property_name)
            return type(p.get(self._nested_property_name))
        else:
            return type(getattr(self._feature, self._property_name))

    def _to_native_type(self, value):
        native_type = self._get_native_type()
        try:
            return native_type(value)
        except:
            return native_type()

    def get_value_as_bool(self):
        try:
            return bool(self._get())
        except:
            return False

    def get_value_as_string(self):
        try:
            return str(self._get())
        except:
            return ''

    def get_value_as_float(self):
        try:
            return float(self._get())
        except:
            return 0.0

    def get_value_as_int(self):
        try:
            return int(self._get())
        except:
            return 0

    def set_value(self, value):
        value = self._to_native_type(value)
        if value != self._get():
            if not self._disable_change:
                self._set(value)
                self._value_changed()
            else:
                self._tmp_value = value

class FeatureListItem(ui.AbstractItem):
    def __init__(self, feature):
        super().__init__()
        self.feature = feature
        self.name_model = FeaturePropertyModel(self.feature, 'name')
        self.active_model = FeaturePropertyModel(self.feature, 'active')

    def __del__(self):
        self.destroy()

    def destroy(self):
        self.active_model.destroy()
        self.feature = None

    def handle_event(self, event):
        return self.name_model.handle_event(event) or self.active_model.handle_event(event)

    def __repr__(self):
        return f'"{self.name_model.as_string} - {self.active_model.as_bool}"'

class FeatureListModel(ui.AbstractItemModel):
    def __init__(self, *args):
        super().__init__()
        self._children = []
        self._features_api = get_state().get_features_api()
        self._subscription = self._features_api.get_event_stream()\
                .create_subscription_to_pop(self._feature_change)
        self._update()

    def __del__(self):
        self.destroy()

    def destroy(self):
        self._subscription.unsubscribe()
        for c in self._children:
            c.destroy()
        self._children = []

    def _update(self):
        self._children = []
        for f in self._features_api.get_features():
            self._children.append(FeatureListItem(f))
        self._refresh()

    def _feature_change(self, event):
        change = event.payload['change']

        # Handle Property Change
        if change['id'] == features_api_module.FeatureChange.PROPERTY_CHANGE['id']:
            for child in self._children:
                change = child.handle_event(event)
                if change:
                    self._refresh(child)
        # Handle Feature Add
        elif change['id'] == features_api_module.FeatureChange.FEATURE_ADD['id']:
            cur_features = [child.feature for child in self._children]
            for feature in self._features_api.get_features():
                if feature not in cur_features:
                    self._children.append(FeatureListItem(feature))
            self._refresh()
        # Handle Feature Remove
        elif change['id'] == features_api_module.FeatureChange.FEATURE_REMOVE['id']:
            features = self._features_api.get_features()
            to_remove = []
            for child in self._children:
                if child.feature not in features:
                    to_remove.append(child)
            for item in to_remove:
                self._children.remove(item)
            self._refresh()
        elif change['id'] in [
                features_api_module.FeatureChange.FEATURE_CLEAR['id'],
                features_api_module.FeatureChange.FEATURE_REORDER['id'],
                ]:
            # full refresh
            self._update()

    def _refresh(self, item=None):
        self._item_changed(item)

    def get_item_children(self, item):
        if item is not None:
            return []
        else:
            return self._children

    def get_item_value_model_count(self, item):
        # num columns
        return 2

    def get_item_value_model(self, item, column_id):
        if column_id == 0:
            return item.name_model
        else:
            return item.active_model

# Wrapper for ui.Label that takes a model to fill its value
class ModelLabel(ui.Label):
    def __init__(self, model, **kwargs):
        super().__init__('', **kwargs)
        self._model = model
        self._update_label()

        self._subscription = self._model.subscribe_value_changed_fn(self._on_model_change)

    def destroy(self):
        self._subscription.unsubscribe()

    def _on_model_change(self, event):
        self._update_label()

    def _update_label(self):
        self.text = self._model.as_string

class FeatureListDelegate(ui.AbstractItemDelegate):
    def __init__(self):
        super().__init__()

    #def build_branch(self, model, item, column_id, level, expanded):
    #    pass

    def build_widget(self, model, item, column_id, level, expanded):
        """Create a widget per column per item"""
        value_model = model.get_item_value_model(item, column_id)
        #label = ui.Label(value_model.as_string)
        if column_id == 0:
            with ui.HStack():
                #field = ui.StringField(value_model, read_only = True, alignment = ui.Alignment.LEFT)
                ui.Spacer(width = 4)
                field = ModelLabel(value_model, alignment = ui.Alignment.LEFT, style_type_name_override = 'TreeView.Item')
        else:
            with ui.HStack(style = {'padding': 0, 'margin': 2} ):
                ui.Spacer()
                field = ui.CheckBox(value_model)

    def build_header(self, column_id):
        if column_id == 0:
            with ui.HStack(style = {'padding': 0, 'margin': 2}):
                #ui.Spacer(width = 4)
                ui.Label('Name', alignment = ui.Alignment.LEFT)
        else:
            with ui.HStack(style = {'padding': 0, 'margin': 2}):
                #ui.Spacer(width = 4)
                ui.Label('Active', alignment = ui.Alignment.CENTER)

class FeaturePropertiesView():
    def __init__(self, model):
        self._model = model
        self._model.set_selection_changed_fn(self._on_selection_changed)
        self._selected_features = self._model.selection

        self._frame = ui.Frame(height = 0)
        self._frame.set_build_fn(self._build_fn)

        state = get_state()
        features_api = state.get_features_api()
        self._subscription = features_api.get_event_stream().\
                create_subscription_to_pop(self._on_feature_change)

    def __del__(self):
        self.destroy()

    def destroy(self):
        self._subscription.unsubscribe()

    def _on_feature_change(self, event):
        change = event.payload['change']

        # Handle Feature Add/Remove/Clear
        if change['id'] in [
                features_api_module.FeatureChange.FEATURE_ADD['id'],
                features_api_module.FeatureChange.FEATURE_REMOVE['id'],
                features_api_module.FeatureChange.FEATURE_CLEAR['id']]:
            self._frame.rebuild()
        if change['id'] in [
                features_api_module.FeatureChange.PROPERTY_CHANGE['id']]:
            # let the value models handle that
            for model in self._property_models:
                model.handle_event(event)

    def _on_selection_changed(self, items):
        self._frame.rebuild()

    def _build_fn(self):
        self._selected_features = [i.feature for i in self._model.selection]

        def build_header(collapsed, title):
            ui.Label(title)

        frame = ui.CollapsableFrame(title='Properties',
                enabled = False, # not collapsable
                style = {'padding':2, 'margin':0}
                )
        frame.set_build_header_fn(build_header)

        if self._selected_features is None or len(self._selected_features) == 0:
            return
        feature = self._selected_features[0]

        self._property_models = []
        self._models = []

        label_width = 100
        line_height = 20
        with frame:
            with ui.VStack(
                    style = {'padding':2, 'margin':1}
                    ):
                # NOTE: callback to update a feature property on an end edit
                # we don't want to update during an edit as this would trigger
                # continuous shader changes
                def feature_property_update(feature, property_name, value_fn, model):
                    setattr(feature, property_name, value_fn())

                with ui.HStack(height = line_height):
                    ui.Label('Name', width = label_width)
                    model = FeaturePropertyModel(feature, 'name')
                    ui.StringField(model, multiline = False, enabled = True)
                    self._property_models.append(model)

                with ui.HStack(height = line_height):
                    ui.Label('Type', width = label_width)
                    ui.StringField(ui.SimpleStringModel(feature.type))

                # delegate by feature type
                # TODO: create feature type delegates
                if feature.type == features_api_module.Image.feature_type:
                    with ui.HStack(height = line_height):
                        ui.Label('Projection', width = label_width)
                        model = ui.SimpleStringModel(feature.projection)
                        self._models.append(model)
                        field = ui.StringField(model, multiline = False, enabled = True)

                    with ui.HStack(height = line_height,
                            style = STYLES):
                        # TODO: Create a dedicated Colormap Widget for this logic
                        ui.Label('colormap', width = label_width)
                        def handle_colormap_dialog(button, feature):
                            def ok_func(dialog):
                                choice = dialog.get_choice()
                                if choice is None:
                                    return
                                dialog.hide()
                                feature.colormap = choice
                                # switch to image button
                                path = get_shader_library().get_colormap_path(choice)
                                button.image_url = path
                                button.text = ''
                            def cancel_func(dialog):
                                dialog.hide()
                            dialog = ColormapDialog(ok_handler=ok_func, cancel_handler=cancel_func)
                            dialog.show()
                        def clear_colormap(button, feature):
                            if feature.colormap is not None:
                                # switch to text button
                                feature.colormap = None
                                button.image_url = ''
                                button.text = 'add'

                        if feature.colormap is not None:
                            colormap_path = get_shader_library().get_colormap_path(feature.colormap)
                            button = ui.Button(image_url=colormap_path, height = line_height, enabled = True,
                                    style={ "Button.Image":{"fill_policy": ui.FillPolicy.STRETCH}} )
                        else:
                            button = ui.Button('add', height = line_height, enabled = True,
                                    style={"Button.Image":{"fill_policy": ui.FillPolicy.STRETCH}})
                        button.set_clicked_fn(partial(handle_colormap_dialog, button, feature))
                        ui.Button(image_url=ICON_PATHS['cancel'], height = line_height, width = line_height, enabled = True,
                                clicked_fn = partial(clear_colormap, button, feature))

                    if feature.remapping is not None:
                        def build_header(collapsed, title):
                            ui.Label(title, width = label_width, height = line_height)

                        frame = ui.CollapsableFrame(title='Remapping', enabled = True)
                        frame.set_build_header_fn(build_header)
                        with frame:
                            def add_remapping_entry(label, name, default, min_value, max_value):
                                with ui.HStack(height = line_height):
                                    ui.Label(label, width = label_width)
                                    model = FeaturePropertyModel(feature, 'remapping', nested_property_name=name)
                                    self._property_models.append(model)
                                    if name not in feature.remapping:
                                        tmp = feature.remapping
                                        tmp[name] = default
                                        feature.remapping = tmp
                                    v = feature.remapping.get(name)
                                    ui.FloatDrag(model, min=min_value, max=max_value, enabled = True)

                            with ui.VStack():
                                add_remapping_entry('Input  Min',   'input_min',    0.0, 0.0, 1.0)
                                add_remapping_entry('Input  Max',   'input_max',    1.0, 0.0, 1.0)
                                add_remapping_entry('Output Min',   'output_min',   0.0, 0.0, 1.0)
                                add_remapping_entry('Output Max',   'output_max',   1.0, 0.0, 1.0)
                                add_remapping_entry('Output Gamma', 'output_gamma', 1.0, 0.0, 2.0)

                    if feature.alpha_sources == feature.sources or feature.alpha_sources == [] or feature.alpha_sources == ['']:
                        with ui.HStack(height = line_height):
                            ui.Label('Use color as alpha', width = label_width)
                            model = ui.SimpleBoolModel()
                            self._models.append(model)
                            def adjust_alpha_source(model):
                                v = model.get_value_as_bool()
                                if v:
                                    feature.alpha_sources = feature.sources
                                else:
                                    feature.alpha_sources = ['']*len(feature.alpha_sources)
                            model.add_value_changed_fn(adjust_alpha_source)
                            ui.CheckBox(model, enabled=True)

                elif feature.type == features_api_module.Sun.feature_type:
                    with ui.HStack(height = line_height):
                        ui.Label('Diurnal Motion', width = label_width)
                        model = FeaturePropertyModel(feature, 'diurnal_motion')
                        self._property_models.append(model)
                        field = ui.CheckBox(model, enabled = True)
                    with ui.HStack(height = line_height):
                        ui.Label('Seasonal Motion', width = label_width)
                        model = FeaturePropertyModel(feature, 'seasonal_motion')
                        self._property_models.append(model)
                        field = ui.CheckBox(model, enabled = True)
                    with ui.HStack(height = line_height):
                        ui.Label('Longitude', width = label_width)
                        model = FeaturePropertyModel(feature, 'longitude')
                        self._property_models.append(model)
                        field = ui.FloatDrag(model, min=0, max=359, step=0.25, enabled=True)
                    with ui.HStack(height = line_height):
                        ui.Label('Latitude', width = label_width)
                        model = FeaturePropertyModel(feature, 'latitude')
                        self._property_models.append(model)
                        field = ui.FloatDrag(model, min=-90, max=90, step=0.25, enabled=True)

                elif feature.type == features_api_module.Curves.feature_type:
                    with ui.HStack(height = line_height):
                        #ui.Label('Color', width = label_width)
                        #model = FeaturePropertyModel(feature, 'color')
                        #field = ui.ColorWidget(enabled=True)
                        #self._property_models['color'] = color
                        ui.Label('Width', width = label_width)
                        model = FeaturePropertyModel(feature, 'width')
                        self._property_models.append(model)
                        field = ui.FloatField(model, enabled=True)

class FeatureAddContextMenu():
    def __init__(self, feature_type_callbacks, **kwargs):
        self._feature_type_callbacks = feature_type_callbacks
        self._menu = None
        self._build_ui()

    def destroy(self):
        self._menu.destroy()
        self._menu = None

    def _build_ui(self):
        pass

    def show(self):
        self._menu = ui.Menu('Context Menu')
        with self._menu:
            for name, callback in self._feature_type_callbacks.items():
                ui.MenuItem(name, triggered_fn=callback)
        self._menu.show()

    def hide(self):
        if self._menu is not None:
            self._menu.hide()

class FeaturePropertiesWindow(ui.Window):
    def __init__(self, title, **kwargs):
        super().__init__(title, **kwargs)
        self.frame.set_build_fn(self._build_fn)
        self._feature_type_callbacks = {}

    def destroy(self):
        self.visible = False
        if hasattr(self, '_tree_view'):
            self._tree_view.destroy()
            self._list_model.destroy()
            self._feature_properties_view.destroy()
        super().destroy()

    def set_feature_type_callbacks(self, callbacks):
        self._feature_type_callbacks = callbacks

    def _build_fn(self):
        with ui.HStack(style = { 'margin':0, 'padding':0 }):
            with ui.VStack(
                    width = ui.Percent(50)):
                with ui.ScrollingFrame(
                        style = { 'padding':0, 'margin':0 },
                        horizontal_scrollbar_policy = ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                        #vertical_scrollbar_policy = ui.ScrollBarPolicy.SCROLLBAR_AS_NEEDED,
                        style_type_name_override = "TreeView"):
                    self._list_model = FeatureListModel()
                    self._list_delegate = FeatureListDelegate()
                    self._tree_view = ui.TreeView(
                            self._list_model, root_visible = False, header_visible = True,
                            width = ui.Percent(100),
                            delegate= self._list_delegate,
                            ennabled = True,
                            style = {})
                    self._tree_view.column_widths = [ui.Fraction(80), ui.Fraction(20)]
                    if self._list_model.get_item_children(None) is not None:
                        self._tree_view.selection = [self._list_model.get_item_children(None)[0]]
                with ui.HStack(height = 24,
                        style = STYLES,
                        ):
                    ui.Spacer()
                    def add_feature_context_menu():
                        self._context_menu = FeatureAddContextMenu(self._feature_type_callbacks)
                        self._context_menu.show()
                    ui.Button(name = 'Add',
                            width = 24,
                            height = 24,
                            tooltip = 'Add new Feature',
                            image_url = ICON_PATHS['add'],
                            clicked_fn=partial(add_feature_context_menu)
                            )
                    def remove_selected_features(tree_view):
                        selection = tree_view.selection
                        features = [s.feature for s in selection]
                        tree_view.selection = []

                        features_api = get_state().get_features_api()
                        for f in features:
                            features_api.remove_feature(f)
                    def set_playback_window_to_selected_features(tree_view, playback_duration=10):
                        selection = tree_view.selection
                        features = [s.feature for s in selection]
                        if not features:
                            features_api = get_state().get_features_api()
                            features = features_api.get_features()
                        time_manager = get_state().get_time_manager()
                        time_manager.include_all_features(playback_duration, features)

                    ui.Spacer(width = 2)

                    def delete_feature_dialog():
                        def ok_handler(dialog):
                            dialog.hide()
                            remove_selected_features(self._tree_view)

                        selected_feature_names = [s.feature.name for s in self._tree_view.selection]
                        if not selected_feature_names:
                            return
                        dialog = MessageDialog(
                                message="Do you really want to delete the selected features?\n" +
                                    '\n'.join(['\t-'+name for name in selected_feature_names]),
                                ok_handler=ok_handler,
                                ok_label="Yes",
                                cancel_label="No")
                        dialog.show()

                    ui.Button(name = 'Remove',
                            width = 24,
                            height = 24,
                            tooltip = 'Remove selected Features',
                            image_url = ICON_PATHS['delete'],
                            #clicked_fn=partial(remove_selected_features, self._tree_view))
                            clicked_fn=delete_feature_dialog)
                    ui.Spacer(width = 2)

                    def focus_input_dialog():
                        def ok_handler(dialog):
                            value = dialog.get_value()
                            if value <= 0:
                                carb.log_error(f'Invalid Playback Duration requested: {value}')
                            else:
                                set_playback_window_to_selected_features(self._tree_view, dialog.get_value())
                                dialog.hide()

                        dialog = InputDialog(input_cls = omni.ui.FloatField,
                                title = 'Set new playback duration',
                                pre_label = 'Playback Duration: ',
                                post_label = 's',
                                default_value = 10.0,
                                ok_handler=ok_handler)
                        dialog.show()

                    ui.Button(name = 'TimeWindowFocus',
                            width = 24,
                            height = 24,
                            tooltip = 'Focus Timeline on selected Features',
                            image_url = ICON_PATHS['time_bracket'],
                            clicked_fn=partial(focus_input_dialog))

            with ui.VStack(
                    width = ui.Percent(50),
                    style = STYLES):
                self._feature_properties_view = FeaturePropertiesView(self._tree_view)
                ui.Spacer()

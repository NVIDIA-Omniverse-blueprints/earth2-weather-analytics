from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core import features_api as features_api_module
from omni.earth_2_command_center.app.shading import get_shader_library

from omni.kit.window.popup_dialog import PopupDialog

from .style import ICON_PATHS

import omni.ui as ui
import omni.kit.ui
import carb.settings

from functools import partial
from typing import Callable, Optional
import asyncio

class ColormapItem(ui.AbstractItem):
    def __init__(self, text):
        super().__init__()
        self.name = text
        self.model = ui.SimpleStringModel(text)

class ColormapItemModel(ui.AbstractItemModel):
    def __init__(self):
        super().__init__()

        shader_library = get_shader_library()
        self._colormaps = get_shader_library().get_colormaps()
        self._items = [ColormapItem(p) for p in self._colormaps]
        self._current_index = omni.ui.SimpleIntModel()
        self._current_index.add_value_changed_fn(self._changed_model)

    def _changed_model(self, model):
        self._item_changed(None)

    def get_item_children(self, item=None):
        if item is None:
            return self._items
        else:
            return []

    def get_item_value_model(self, item = None, column_id = None):
        if item is None:
            return self._current_index
        return item.model

    def get_item_value_model_count(self, item=None):
        return 1

class ColormapListItem(ui.AbstractItem):
    def __init__(self, name):
        super().__init__()
        self.name = name
        self.model = ui.SimpleStringModel(name)

    def __del__(self):
        self.destroy()

    def destroy(self):
        pass

class ColormapListModel(ui.AbstractItemModel):
    def __init__(self, *args):
        super().__init__()
        self._children = []
        self._update()

    def __del__(self):
        self.destroy()

    def destroy(self):
        for c in self._children:
            c.destroy()
        self._children = []

    def _update(self):
        shader_library = get_shader_library()
        colormaps = get_shader_library().get_colormaps()

        self._children = []
        for name in colormaps:
            self._children.append(ColormapListItem(name))
        self._refresh()

    def _refresh(self, item=None):
        self._item_changed(item)

    def get_item_children(self, item):
        if item is not None:
            return []
        else:
            return self._children

    def get_item_value_model_count(self, item):
        # num columns
        return 1

    def get_item_value_model(self, item, column_id):
        return item.model

class ColormapListDelegate(ui.AbstractItemDelegate):
    def __init__(self):
        self._shader_library = get_shader_library()
        super().__init__()

    def build_widget(self, model, item, column_id, level, expanded):
        """Create a widget per column per item"""
        name = item.name
        path = self._shader_library.get_colormap_path(name)
        with ui.HStack():
            ui.Label(name, width = 120)
            ui.Spacer(width = 4)
            ui.Image(path, fill_policy = ui.FillPolicy.STRETCH)

class ColomapEntryButton():
    def __init__(self, name, **kwargs):
        self.name = name
        shader_library = get_shader_library()
        self.path = shader_library.get_colormap_path(name)
        self.selected = False
        self._clicked_fn = None

        self._stack = ui.ZStack(width = ui.Percent(100), height = 20,
                style = {
                    ':hovered':{'background_color':0x44FFFFFF},
                    'Rectangle.Selected':{'background_color':0x44FFFFFF},
                    'Rectangle.Unselected':{'background_color':0x00FFFFFF},
                    })
        with self._stack:
            ui.InvisibleButton(clicked_fn=self._on_click)
            self._rect = ui.Rectangle(style_type_name_override = 'Rectangle.Unselected')

            with ui.HStack(style = {'margin':2}):
                ui.Label(self.name, width = 120)
                ui.Image(self.path, fill_policy = ui.FillPolicy.STRETCH)

    def set_on_clicked_fn(self, fn):
        self._clicked_fn = fn

    @property
    def visible(self):
        return self._stack.visible

    @visible.setter
    def visible(self, v):
        self._stack.visible = bool(v)

    def unselect(self):
        self.selected = False
        self._rect.style_type_name_override = 'Rectangle.Unselected'

    def _on_click(self):
        self.selected = True
        self._rect.style_type_name_override = 'Rectangle.Selected'
        if self._clicked_fn is not None:
            self._clicked_fn(self)

class ColormapDialog(PopupDialog):
    __default_message = 'search...'

    def __init__(self,
        ok_handler: Optional[Callable[[PopupDialog], None]]=None,
        cancel_handler: Optional[Callable[[PopupDialog], None]]=None,
        warning_message: Optional[str]=None
    ):
        self._selected_item = None

        self._search_model = ui.SimpleStringModel(ColormapDialog.__default_message)
        def clear_on_edit(model):
            if model.get_value_as_string() == ColormapDialog.__default_message:
                model.set_value('')
        def reset_after_edit(model):
            if model.get_value_as_string() == '':
                model.set_value(ColormapDialog.__default_message)
        self._search_model.add_value_changed_fn(self._search)
        self._search_model.add_begin_edit_fn(clear_on_edit)
        self._search_model.add_end_edit_fn(reset_after_edit)

        super().__init__(
            width = 400,
            title = 'Colormap Chooser',
            ok_handler = ok_handler,
            cancel_handler = cancel_handler,
            hide_title_bar = False,
            modal = True,
            warning_message = warning_message
                )

    def __del__(self):
        self.destroy()

    def destroy(self):
        super().destroy()

    def hide(self):
        super().hide()

    def get_choice(self):
        if self._selected_item is not None:
            return self._selected_item.name
        else:
            return None

    def _build_widgets(self):
        with self._window.frame:
            line_height = 20
            with ui.VStack(style={'padding':4, 'margin':4}):
                ui.StringField(self._search_model, allow_tab_input=False, multiline=False)

                with ui.ScrollingFrame(
                        height = 300,
                        style = { 'padding':0, 'margin':0 },
                        horizontal_scrollbar_policy = ui.ScrollBarPolicy.SCROLLBAR_ALWAYS_OFF,
                        style_type_name_override = "TreeView"):
                    with ui.VStack():
                        shader_library = get_shader_library()
                        colormaps = get_shader_library().get_colormaps()
                        colormaps.sort(key=str.lower)
                        self._colormap_entry_buttons = {}
                        for name in colormaps:
                            button = ColomapEntryButton(name)
                            button.set_on_clicked_fn(self._selection_changed)
                            self._colormap_entry_buttons[name] = button

                ui.Spacer()
                self._build_ok_cancel_buttons(disable_cancel_button=False)

    def _search(self, model):
        search_keyword = model.get_value_as_string().lower()
        keys = list(self._colormap_entry_buttons.keys())

        if search_keyword == ColormapDialog.__default_message.lower():
            for k in keys:
                self._colormap_entry_buttons[k].visible = True
        else:
            for k in keys:
                self._colormap_entry_buttons[k].visible = search_keyword in k.lower()

    def _selection_changed(self, item):
        if self._selected_item is not None:
            self._selected_item.unselect()
        self._selected_item = item


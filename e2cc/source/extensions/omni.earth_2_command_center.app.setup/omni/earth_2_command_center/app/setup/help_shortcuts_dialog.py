# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from typing import Callable, Optional

from omni.kit.window.popup_dialog import PopupDialog
import omni.kit.hotkeys.core
import omni.kit.actions.core

#from .style import ICON_PATHS

import omni.ui as ui
import omni.kit.ui
import carb.settings


class HelpShortcutsDialog(PopupDialog):
    def __init__(self,
        ok_handler: Callable[[PopupDialog], None]=None,
        cancel_handler: Callable[[PopupDialog], None]=None,
        warning_message: Optional[str]=None
    ):
        super().__init__(
            width = 400,
            title = 'Shortcuts',
            ok_handler = (ok_hander if ok_handler is not None else self._ok_handler),
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

    def _build_widgets(self):
        hotkeys_registry = omni.kit.hotkeys.core.get_hotkey_registry() 
        hotkeys = hotkeys_registry.get_all_hotkeys()

        actions_registry = omni.kit.actions.core.acquire_action_registry() 

        with self._window.frame:
            line_height = 20
            with ui.VStack():
                with ui.ScrollingFrame(
                        height = 300,
                        style = { 'padding':0, 'margin':2 },
                        style_type_name_override = "TreeView"):
                    with ui.VStack():
                        ui.Spacer(height=0.5*line_height)
                        for h in hotkeys:
                            if h.hotkey_ext_id.startswith('omni.earth_2_command_center.app'):
                                cur_action = h.action
                                with ui.HStack():
                                    ui.Label(cur_action.display_name, width=200)
                                    ui.Label(h.key_text, width=80)
                                with ui.HStack():
                                    ui.Spacer(width=200)
                                    ui.Label(cur_action.description, word_wrap=True)
                                ui.Spacer(height=0.5*line_height)
                                ui.Line()
                                ui.Spacer(height=0.5*line_height)

                ui.Spacer()
                self._build_ok_cancel_buttons(disable_cancel_button=True)

    @staticmethod
    def _ok_handler(dialog):
        dialog.hide()


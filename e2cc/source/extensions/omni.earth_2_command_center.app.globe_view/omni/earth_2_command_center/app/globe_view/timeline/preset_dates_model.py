# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import omni.ui as ui

class PresetDateModel(ui.AbstractValueModel):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.active_button = None
        self._on_toggled_function = None

    def __del__(self):
        self.destroy()

    def destroy(self):
        self.buttons = []
        self.active_button = None

    def get_value_as_bool(self):
        if self.active_button:
            return True

        return False

    def set_value(self, value: bool):
        if not self.active_button:
            return

        if value:
            self.active_button.checked = True
        else:
            self.active_button.checked = False

    def append(self, button):
        if (button in self.buttons):
            return

        self.buttons.append(button)

    def get_active_button(self):
        if self.active_button:
            return self.active_button

        return None

    def set_active_button(self, clicked_btn: ui.Circle):
        for button in self.buttons:
            button.checked = False
            if button.name == clicked_btn.name:
                button.checked = True
                self.active_button = button

                if self._on_toggled_function:
                    self._on_toggled_function()

    def set_toggled_fn(self, on_toggled_fn):
        self._on_toggled_function = on_toggled_fn

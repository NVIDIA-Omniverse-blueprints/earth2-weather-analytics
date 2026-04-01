# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb
import omni.ext

from .ui.main import AviationWindow


class AviationUIExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._ext_id = ext_id
        self._frame_count = 0
        self._window = None

        self._update_event = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self._on_update, name="Aviation UI")
        )

    def _on_update(self, event):
        self._frame_count += 1
        if self._frame_count >= 100:
            self._start_extension_logic()
            self._update_event.unsubscribe()

    def _start_extension_logic(self):
        carb.log_info("Aviation UI Extension Start Up")
        self._add_window()

    def _add_window(self):
        if hasattr(self, "_window") and self._window:
            self._window.show()
            return
        self._window = AviationWindow()
        self._window.build_window()

    def on_shutdown(self):
        if self._window:
            self._window.shutdown()
            self._window = None

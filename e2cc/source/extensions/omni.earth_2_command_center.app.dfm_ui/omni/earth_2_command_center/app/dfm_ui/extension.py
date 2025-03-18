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
import omni
import asyncio
import omni.kit.async_engine
import omni.earth_2_command_center.app.window.feature_properties as feature_properties

from .ui import ExtensionWindow

# class WaitForRtx:
#     """
#     Helper class to wait for RTX to load
#     """

#     def __init__(self):
#         self._wait = asyncio.Event()
#         self._sub = (
#             omni.usd.get_context()
#             .get_rendering_event_stream()
#             .create_subscription_to_push_by_type(int(omni.usd.StageRenderingEventType.NEW_FRAME), self._set_ready)
#         )

#     async def wait(self):
#         await self._wait.wait()

#     def _set_ready(self, _):
#         self._wait.set()
#         self._sub.unsubscribe()
#         self._sub = None


# class WaitForStageLoad:
#     """
#     Helper class to wait for Stage to load
#     """

#     def __init__(self):
#         self._wait = asyncio.Event()
#         self._sub = (
#             omni.usd.get_context()
#             .get_stage_event_stream()
#             .create_subscription_to_push_by_type(int(omni.usd.StageEventType.ASSETS_LOADED), self._set_ready)
#         )

#     async def wait(self):
#         await self._wait.wait()

#     def _set_ready(self, _):
#         self._wait.set()
#         self._sub.unsubscribe()
#         self._sub = None


# async def wait_for_rtx_and_stage_then_init():
#     await WaitForRtx().wait()
#     await WaitForStageLoad().wait()
# initialize()


class DfmUIExtension(omni.ext.IExt):

    def on_startup(self, ext_id):
        self._ext_id = ext_id
        self._frame_count = 0

        # Register a frame callback
        self._update_event = (
            omni.kit.app.get_app()
            .get_update_event_stream()
            .create_subscription_to_pop(self._on_update, name="DFM UI")
        )

    def _on_update(self, event):
        self._frame_count += 1

        if self._frame_count >= 100:
            self._start_extension_logic()
            self._update_event.unsubscribe()

    def _start_extension_logic(self):
        # try:
        #     omni.kit.async_engine.run_coroutine(wait_for_rtx_and_stage_then_init())
        # except:
        #     pass
        carb.log_info("DFM UI Extension Start Up")
        # feature_properties.get_instance().register_feature_type_add_callback("Data Federation Mesh", self._add_window)
        self._add_window()

    def _add_window(self):
        # Nothing to do if we are already built the window, just make sure it is visible
        if hasattr(self, "_window"):
            self._window.show()
            return

        self._window = ExtensionWindow()
        self._window.build_window()

    def on_shutdown(self):
        pass

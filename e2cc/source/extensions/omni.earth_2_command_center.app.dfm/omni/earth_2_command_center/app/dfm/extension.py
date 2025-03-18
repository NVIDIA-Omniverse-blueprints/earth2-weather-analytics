# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



import omni
import asyncio
import omni.kit.async_engine


class WaitForRtx:
    """
    Helper class to wait for RTX to load
    """

    def __init__(self):
        self._wait = asyncio.Event()
        self._sub = (
            omni.usd.get_context()
            .get_rendering_event_stream()
            .create_subscription_to_push_by_type(
                int(omni.usd.StageRenderingEventType.NEW_FRAME), self._set_ready
            )
        )

    async def wait(self):
        await self._wait.wait()

    def _set_ready(self, _):
        self._wait.set()
        self._sub.unsubscribe()
        self._sub = None


class WaitForStageLoad:
    """
    Helper class to wait for Stage to load
    """

    def __init__(self):
        self._wait = asyncio.Event()
        self._sub = (
            omni.usd.get_context()
            .get_stage_event_stream()
            .create_subscription_to_push_by_type(
                int(omni.usd.StageEventType.ASSETS_LOADED), self._set_ready
            )
        )

    async def wait(self):
        await self._wait.wait()

    def _set_ready(self, _):
        self._wait.set()
        self._sub.unsubscribe()
        self._sub = None


async def wait_for_rtx_and_stage_then_init():
    await WaitForRtx().wait()
    await WaitForStageLoad().wait()
    # initialize()


class DfmExtension(omni.ext.IExt):
    def on_startup(self, _ext_id: str):
        try:
            omni.kit.async_engine.run_coroutine(wait_for_rtx_and_stage_then_init())
        except:
            pass

    def on_shutdown(self):
        pass

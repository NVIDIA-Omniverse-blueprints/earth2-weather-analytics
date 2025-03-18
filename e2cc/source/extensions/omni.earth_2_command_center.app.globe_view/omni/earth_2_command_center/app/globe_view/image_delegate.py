# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['ImageDelegate']

import numpy as np
import asyncio
import traceback

from pxr import Sdf

import carb
import omni.kit.renderer.bind
import omni.kit.async_engine as async_engine
import omni.kit.actions.core
import omni.kit.hotkeys.core

from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features_api as features_api
import omni.earth_2_command_center.app.shading as e2_shading

from .utils import *

class ImageDelegate:
    def __init__(self, viewport):
        self._viewport = viewport
        self._shader_creation_task = None
        self._shader_recompilation_event = None#asyncio.Event()

        # layered material setup
        self._layered_material_path = Sdf.Path('/World/Looks/LayeredShellMat')
        self._globe_prim_path = Sdf.Path('/World/earth_xform/diamond_globe')

        renderer = omni.kit.renderer.bind.get_renderer_interface()
        self._render_subscription = renderer.get_pre_begin_frame_event_stream().create_subscription_to_pop(self._on_begin_frame)

        #self._schedule_layered_shell_recompilation()

        # register actions and hotkeys
        # TODO: this is not required per viewport and should be done globally
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.register_action(viewport.ext_id, 'refresh', self._schedule_layered_shell_recompilation, 'Refresh Shader', 'Refresh Shader Graph in case of corrupt graph state')
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.register_hotkey(viewport.ext_id, 'F5', viewport.ext_id, 'refresh')

        self._update_mapping = {}

        # if there already are image features present, this will pick them up
        self._schedule_layered_shell_recompilation()

    def __del__(self):
        if self._shader_creation_task:
            self._shader_creation_task.cancel()
            self._shader_creation_task = None

        self._shader_recompilation_event = None
        if self._render_subscription is not None:
            self._render_subscription.unsubscribe()

        # deregister actions and hotkeys
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.deregister_action(self._viewport.ext_id, 'refresh', self._schedule_layered_shell_recompilation)
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.deregister_hotkey(self._viewport.ext_id, 'F5')

    def __call__(self, event, globe_view):
        change = event.payload['change']
        id = event.sender
        feature = get_state().get_features_api().get_feature_by_id(id)

        if change['id'] in [
                features_api.FeatureChange.FEATURE_ADD['id'],
                features_api.FeatureChange.FEATURE_REMOVE['id'],
                features_api.FeatureChange.FEATURE_CLEAR['id'],
                ]:
            self._schedule_layered_shell_recompilation()

        elif change['id'] in [
                features_api.FeatureChange.FEATURE_REORDER['id'],
                ]:
            # TODO: we could change the connection order but that would still
            # trigger a long MDL recompilation
            permutation_list = list(event.payload["permutation"])
            self._schedule_layered_shell_recompilation()

        elif change['id'] == features_api.FeatureChange.PROPERTY_CHANGE['id']:
            property_name = event.payload['property']
            # property blacklist which doesn't need recompilation
            blacklist = [ 'name', 'time_coverage' ]
            if property_name in blacklist:
                return

            # handle shader network property update
            feature_id = event.sender
            if feature_id in self._update_mapping and property_name in self._update_mapping[feature_id]:
                update_done = True
                for update_callback in self._update_mapping[feature_id][property_name]:
                    update_done = update_done and update_callback(event.payload)
                if update_done:
                    return
            # unhandled, so recompile the graph
            self._schedule_layered_shell_recompilation()
        else:
            carb.log_warn(f"Unhandled change: {change['name']}")

    def _on_begin_frame(self, event):
        # create it the worker on the first frame as this is when we can create usd content
        if self._shader_creation_task is None:
            self._render_subscription = None
            self._schedule_layered_shell_recompilation()
            self._shader_creation_task = async_engine.run_coroutine(self._recompile_layered_shell_worker())

    # indicate that the main layered shell material needs a rebuild
    def _schedule_layered_shell_recompilation(self):
        if self._shader_recompilation_event is None:
            self._shader_recompilation_event = asyncio.Event()
        self._shader_recompilation_event.set()

    # persistent task that will trigger the actual recompilation of the main
    # layered shell material
    async def _recompile_layered_shell_worker(self):
        while True:
            try:
                await self._shader_recompilation_event.wait()
                self._shader_recompilation_event.clear()
                material_prim, self._update_mapping = \
                        e2_shading.create_layered_shell_material(self._viewport.usd_stage, self._layered_material_path,
                                self._globe_prim_path,
                                get_state().get_features_api().get_image_features())
            except asyncio.CancelledError:
                carb.log_warn(f'Cancelled Task')
                break
            except Exception as e:
                carb.log_error(f'Exception triggered during recompilation: {e}')
                traceback.print_exc()

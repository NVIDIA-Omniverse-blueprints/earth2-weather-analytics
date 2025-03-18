# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import os
from typing import Dict, List, Union
from pathlib import Path
import asyncio

import carb
import carb.tokens
from carb.settings import get_settings

from omni.kit.quicklayout import QuickLayout
from omni.kit.window.title import get_main_window_title
from omni.kit.menu.utils import add_menu_items, remove_menu_items, MenuItemDescription

import omni.ext
import omni.kit.actions.core
import omni.kit.app
import omni.kit.hotkeys.core
import omni.splash
import omni.timeline
import omni.ui as ui
import omni.usd

from pxr import Usd, UsdGeom, Gf, Sdf

from omni.earth_2_command_center.app.core.utils import latlong_rect_to_affine_mapping, affine_mapping_to_shader_param_value
from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.geo_utils import get_geo_converter

from .help_shortcuts_dialog import HelpShortcutsDialog

EXTENSION_FOLDER_PATH = Path(
    omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)
)

async def _load_layout(layout_file: str):
    """this private methods just help loading layout, you can use it in the Layout Menu"""
    await omni.kit.app.get_app().next_update_async()
    if os.path.exists(layout_file):
        QuickLayout.load_file(layout_file)

# This extension is mostly loading the Layout updating menu
class SetupExtension(omni.ext.IExt):
    # ext_id is current extension id. It can be used with extension manager to query additional information, like where
    # this extension is located on filesystem.
    def on_startup(self, ext_id):
        self._ext_id = ext_id
        self._apply_settings()
        self._await_layout = asyncio.ensure_future(self._delayed_layout())

        self._add_base_layer()

        # setup the Application Title
        window_title = get_main_window_title()
        settings = get_settings()
        window_title.set_app_version(settings.get("/app/titleVersion"))

        try:
            from omni.kit.mainwindow import get_main_window
            main_window = get_main_window()
            settings_path = "/app/mainMenuBar/visible"
            settings.set_default_bool(settings_path, True)
            main_window.get_main_menu_bar().visible = settings.get_as_bool(settings_path)
        except ImportError:
            carb.log_warn("[omni.earth_2_command::setup] Failed to remove the main menu bar and status bar")

        # Register Play/Pause/Stop Hotkeys for playback
        def play():
            timeline = omni.timeline.get_timeline_interface()
            if timeline.is_playing():
                timeline.pause()
            else:
                timeline.play()
        def stop():
            timeline = omni.timeline.get_timeline_interface()
            timeline.stop()
            timeline.set_current_time(timeline.get_start_time())
        def quit():
            omni.kit.app.get_app().post_quit()
        def export_session():
            from omni.kit.window.filepicker import FilePickerDialog
            def on_click(dialog, filename, dirname):
                stage = omni.usd.get_context().get_stage()
                if stage is None:
                    carb.log_error(f'No Stage open to export')
                    dialog.hide()
                carb.log_warn(f'Exporting to {dirname}{filename}')
                #stage.GetSessionLayer().Export(f'{dirname}{filename}')
                #stage.Export(f'{dirname}{filename}')
                out_stage = Usd.Stage.Open(stage.GetRootLayer())
                out_stage.GetLayerStack().insert(0, stage.GetSessionLayer())
                out_stage.Export(f'{dirname}{filename}')
                dialog.hide()

            dialog = FilePickerDialog(
                    'Export Session',
                    apply_button_label = 'Export',
                    show_detail_view = False,
                    enable_checkpoints = False,
                    click_apply_handler = lambda filename, dirname: on_click(dialog, filename, dirname))

        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.register_action(self._ext_id, 'play', play, 'Play/Pause', 'Play/Pause Playback')
        action_registry.register_action(self._ext_id, 'stop', stop, 'Stop', 'Stop and Reset Playback')
        action_registry.register_action(self._ext_id, 'quit', quit, 'Quit', 'Quit Application')
        action_registry.register_action(self._ext_id, 'export_session', export_session, 'Export Session', 'Serialize USD State to File')
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.register_hotkey(self._ext_id, 'CTRL + SPACE', self._ext_id, 'stop')
        hotkey_registry.register_hotkey(self._ext_id, 'SPACE', self._ext_id, 'play')
        hotkey_registry.register_hotkey(self._ext_id, 'CTRL + S', self._ext_id, 'export_session')

        def toggle_stats():
            import carb.settings
            settings = carb.settings.get_settings()

            hud_setting_paths = [
                '/persistent/app/viewport/Globe View/Viewport0/hud/renderResolution/visible',
                '/persistent/app/viewport/Globe View/Viewport0/hud/renderFPS/visible',
                '/persistent/app/viewport/Globe View/Viewport0/hud/deviceMemory/visible',
                '/persistent/app/viewport/Globe View/Viewport0/hud/hostMemory/visible',
                ]
            next_value = not settings.get_as_bool(hud_setting_paths[0])
            for hud_setting_path in hud_setting_paths:
                settings.set_bool(hud_setting_path, next_value)

        action_registry.register_action(self._ext_id, 'toggle_stats', toggle_stats, 'Toggle Stats', 'Toggle Stats')
        hotkey_registry.register_hotkey(self._ext_id, 'F8', self._ext_id, 'toggle_stats')

        def switch_renderer():
            import carb.settings
            settings = carb.settings.get_settings()
            cur = settings.get("/rtx/rendermode")
            if cur == "rtx":
                settings.set_string("/rtx/rendermode", "PathTracing")
            else:
                settings.set_string("/rtx/rendermode", "rtx")

        action_registry.register_action(self._ext_id, 'switch_renderer', switch_renderer, 'Switch Renderer', 'Toggle between Real-Time and Path Tracing RTX Renderer')
        hotkey_registry.register_hotkey(self._ext_id, 'F9', self._ext_id, 'switch_renderer')

        # TODO: This belongs into the Viewport Extensions
        ctx = omni.usd.get_context()
        ctx.new_stage()

        # need to call this to ensure the stage's time codes are initialized correctly.
        # TODO: there must be some event that we can listen to in core.TimeManager instead
        # to sync the stage automatically when its created.
        get_state().get_time_manager().sync_stage()

        # ===============================================================================
        # OM-98588: These two settings do not co-operate well on ADA cards, so for
        # now simulate a toggle of the present thread on startup to work around
        if settings.get("/exts/omni.kit.renderer.core/present/enabled"):
            async def _toggle_present(settings, n_waits: int = 1):
                async def _toggle_setting(app, enabled: bool, n_waits: int):
                    for _ in range(n_waits):
                        await app.next_update_async()
                    settings.set("/exts/omni.kit.renderer.core/present/enabled", enabled)

                app = omni.kit.app.get_app()
                await _toggle_setting(app, False, n_waits)
                await _toggle_setting(app, True, n_waits)

            asyncio.ensure_future(_toggle_present(settings, 5))
        # ===============================================================================

    def _apply_settings(self):
        settings = carb.settings.get_settings()
        tokens = carb.tokens.get_tokens_interface()

        ext_name = omni.ext.get_extension_name(self._ext_id)
        world_texture_base_path_setting = settings.get(f"/exts/{ext_name}/worldTextureBasePath")
        if isinstance(world_texture_base_path_setting, list):
            for i,s in enumerate(world_texture_base_path_setting):
                world_texture_base_path_setting[i] = tokens.resolve(s)
        else:
            world_texture_base_path_setting = tokens.resolve(world_texture_base_path_setting)
        self._world_texture_base_path = world_texture_base_path_setting

    async def _delayed_layout(self):
        # few frame delay to allow automatic Layout of window that want their own positions
        for i in range(4):
            await omni.kit.app.get_app().next_update_async()

        try:
            ext_name = omni.ext.get_extension_name(self._ext_id)
            settings = carb.settings.get_settings()
            # setup the Layout for your app
            layouts_path = carb.tokens.get_tokens_interface().resolve(f"${{{ext_name}}}/layouts")
            layout_file = Path(layouts_path).joinpath(f"{settings.get('/app/layout/name')}.json")
            asyncio.ensure_future(_load_layout(f"{layout_file}"))

            # set cache of dynamictexture
            import hpcvis.dynamictexture
            dt = hpcvis.dynamictexture.acquire_dynamic_texture_interface()
            cache_size = settings.get(f"/exts/{ext_name}/dynamic_texture_cache_size")
            if isinstance(cache_size, int):
                dt.cache_size = cache_size
            elif isinstance(cache_size, str):
                # check if it's a percentage
                import re
                pattern = r'(\d+(?:\.\d+)?)%'
                match = re.search(pattern, cache_size)
                if match:
                    percentage = float(match.group(1))/100
                    import omni.resourcemonitor as rm
                    res_interface = rm.acquire_resource_monitor_interface()
                    max_memory = res_interface.get_total_host_memory()
                    dt.cache_size = max(0, min(max_memory, int(max_memory*percentage)))
            carb.log_warn(f'Setting Dynamic Texture Cache Size set to {dt.cache_size/(2**30):.2f}GB')
            dt.sync = False

            # setting up actions
            action_registry = omni.kit.actions.core.acquire_action_registry()
            def toggle_dynamic_texture_sync():
                dt = hpcvis.dynamictexture.acquire_dynamic_texture_interface()
                dt.sync = not dt.sync

            def dynamic_texture_sync_state():
                dt = hpcvis.dynamictexture.acquire_dynamic_texture_interface()
                return dt.sync

            # Add Rendering Menu Entries
            action_registry.register_action(self._ext_id,
                    'dynamictexture.sync', toggle_dynamic_texture_sync, 'DynamicTexture Sync', 'Toggle synchronization of dynamic texture loading with rendering of viewport frames')
            menu_entry = MenuItemDescription("Dynamic Texture",
                    sub_menu=[MenuItemDescription("Sync with Renderer", ticked=False,
                        ticked_fn=dynamic_texture_sync_state,
                        onclick_action=(self._ext_id, 'dynamictexture.sync'))])
            add_menu_items([menu_entry], name="Rendering")

            # Add Help Menu Entries
            def help_menu():
                dialog = HelpShortcutsDialog()
                dialog.show()
            action_registry.register_action(self._ext_id,
                    'shortcuts', help_menu, 'Show Shortcuts', 'Show Shortcuts Window')
            menu_entry = MenuItemDescription("Hotkeys",
                        onclick_action=(self._ext_id, 'shortcuts'))
            add_menu_items([menu_entry], name="Help", menu_index=99)
        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            omni.splash.acquire_splash_screen_interface().close_all()

    def _add_base_layer(self):
        import numpy as np
        ## create implicit base layer to hold base earth map
        state = omni.earth_2_command_center.app.core.get_state()
        features_api = state.get_features_api()
        img = features_api.create_image_feature()
        img.name = 'Base Satellite'
        if isinstance(self._world_texture_base_path, list):
            num_imgs = len(self._world_texture_base_path)
            def get_split(num_imgs):
                import math
                a = int(math.sqrt(num_imgs/2))
                if 2*a*a == num_imgs:
                    return (2*a, a)
                a = int(math.sqrt(num_imgs))
                if a*a == num_imgs:
                    return (a,a)
                return None # unhandled

            split = get_split(num_imgs)
            if not split:
                carb.log_error(f'Could not determine split for {num_imgs} images')
                return
            if split not in [(1,1), (2,1), (2,2), (4,2)]:
                carb.log_error(f'Unsupported Split requested: {split}')
                return
            if split == (1,1):
                img.projection = 'latlong'
                img.sources = self._world_texture_base_path
            else:
                img.projection = f'latlong_{split[0]}_{split[1]}'
                img.sources = self._world_texture_base_path
        else:
            img.projection = 'latlong'
            img.sources = [self._world_texture_base_path]
        img.longitudinal_offset = -np.pi
        features_api.add_feature(img)

        ## NOTE: example of how to add a high resolution inset
        #img = features_api.create_image_feature()
        #img.name = 'Base Satellite Taiwan Inset'
        #img.projection = 'latlong'
        #img.longitudinal_offset = -np.pi
        ##base_path = '/home/phadorn/workspace/material/textures/earth/earth/world_{tile}_{res}.jpg'
        #base_path = 'omniverse://hpcviz.ov.nvidia.com/Demos/E2Base/textures/earth/world_{tile}_{res}.jpg'
        #img.sources = [base_path.format(tile='D1', res='16k')]
        #img.alpha_sources = ['']
        #img.affine = affine_mapping_to_shader_param_value(
        #        latlong_rect_to_affine_mapping(lon_min = 3/4*2*np.pi, lon_max = 2*np.pi, lat_min=0.0, lat_max=np.pi/2))
        #features_api.add_feature(img)

        # NOTE: example of how to add latlong splits at various resolutions
        #img = features_api.create_image_feature()
        #img.name = 'Base Satellite'
        #img.projection = 'latlong_4_2'
        #img.longitudinal_offset = -np.pi
        #base_path = '/home/nvidia/Downloads/earth/world_{tile}_{res}.jpg'
        #img.sources = [
        #        base_path.format(tile='A1', res='16k'),
        #        base_path.format(tile='B1', res='16k'),
        #        base_path.format(tile='C1', res='16k'),
        #        base_path.format(tile='D1', res='16k'),
        #        base_path.format(tile='A2', res='16k'),
        #        base_path.format(tile='B2', res='16k'),
        #        base_path.format(tile='C2', res='16k'),
        #        base_path.format(tile='D2', res='16k')
        #        ]
        #features_api.add_feature(img)

        ## NOTE: example of how to add a high resolution inset
        #img = features_api.create_image_feature()
        #img.name = 'Taiwan'
        #img.projection = 'latlong_2_2'
        #img.longitudinal_offset = 0
        ##base_path = 'omniverse://hpcviz.ov.nvidia.com/Demos/gtc_2024_corrdiff/taiwan_maps/final_{u}_{v}_{ver}.jpg'
        #base_path = '/tmp/final_{u}_{v}_{ver}.jpg'
        #img.sources = [
        #        base_path.format(u=0, v=0, ver='edit'),
        #        base_path.format(u=0, v=1, ver='edit'),
        #        base_path.format(u=1, v=0, ver='edit'),
        #        base_path.format(u=1, v=1, ver='edit')
        #        ]
        #img.alpha_sources = [
        #        base_path.format(u=0, v=0, ver='mask'),
        #        base_path.format(u=0, v=1, ver='mask'),
        #        base_path.format(u=1, v=0, ver='mask'),
        #        base_path.format(u=1, v=1, ver='mask')
        #        ]
        #img.affine = affine_mapping_to_shader_param_value(
        #        latlong_rect_to_affine_mapping(lon_min = 119.0, lon_max = 123, lat_min=21.5, lat_max=25.5, is_in_radians=False))
        #features_api.add_feature(img)

    def on_shutdown(self):
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.deregister_all_hotkeys_for_extension(self._ext_id)
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.deregister_all_actions_for_extension(self._ext_id)

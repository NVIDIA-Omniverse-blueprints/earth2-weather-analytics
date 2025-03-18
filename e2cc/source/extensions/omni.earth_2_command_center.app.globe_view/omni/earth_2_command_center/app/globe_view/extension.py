# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['get_globe_view', 'WindowExtension']

import asyncio
import numpy as np
import time

import omni.ext
import omni.kit.app
import omni.kit.ui
import omni.kit.renderer.bind

import carb

import omni.kit.viewport.utility
from omni.kit.viewport.utility import get_active_viewport

import omni.timeline
import omni.kit.actions.core
import omni.kit.hotkeys.core

import omni.earth_2_command_center.app.core
import omni.earth_2_command_center.app.core.features_api as features_api
import omni.earth_2_command_center.app.core.sun_motion as sun_motion
import omni.earth_2_command_center.app.shading as e2_shading
from omni.earth_2_command_center.app.geo_utils import get_geo_converter

from .globe_scene import GlobeScene
from .globe_ui import GlobeUI
from .render_settings import set_render_settings
from .utils import toggle_visibility

# delegates to handle render state in viewport
from .curves_delegate import CurvesDelegate
from .image_delegate import ImageDelegate

from pxr import UsdGeom, Sdf, Tf, Usd, Gf

def get_globe_view():
    global _globe_view
    return _globe_view

class WindowExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._ext_id = ext_id
        global _globe_view
        _globe_view = self

        self._usd_ready = False

        self._timeline = omni.timeline.get_timeline_interface()
        self._tick_event_subscription = None
        self._last_tick_time = None

        state = omni.earth_2_command_center.app.core.get_state()
        self._features_api = state.get_features_api()
        self._time_manager = state.get_time_manager()

        # Features that the GlobeView needs to manage
        # TODO: we should expect others to be able to create these features and
        # we should handle the situation where these features are already present
        # on startup
        self._sun_feature = None
        self._sun_feature_motion: sun_motion.SunMotion = None
        self._headlight_feature = None
        self._ambient_light_feature = None
        self._atmos_feature = None
        self._add_sun_feature()
        self._add_headlight_feature()
        self._add_ambient_light_feature()
        self._add_atmos_feature()

        self._earth_radius = 4950

        # subscribe to feature events to GlobeView can react to changes
        self._feature_subscription = self._features_api.get_event_stream().create_subscription_to_push(self._on_feature_change)

        # create timeline subscription
        event_stream = self._time_manager.get_timeline_event_stream()
        self._timeline_subscription = event_stream.create_subscription_to_pop(self._on_time)

        # 'soft' dependency to FeatureProperties Window
        # we add hooks that get called when the extension gets loaded/unloaded
        # so we can enable/disable features that depend on FeatureProperties
        ext_manager = omni.kit.app.get_app_interface().get_extension_manager()
        feature_properties_ext_name = 'omni.earth_2_command_center.app.window.feature_properties'

        # register callbacks for when feature properties window is enabled/disabled
        # if the extension is already loaded, the callback is triggered immediately
        self._registered_names = []
        self._feature_properties_hook = ext_manager.subscribe_to_extension_enable(
                self._on_feature_properties_enable,
                self._on_feature_properties_disable,
                feature_properties_ext_name)

        # feature type delegate callbacks
        self._feature_type_delegates = []

        # main ui
        self._screen_ui = None

        # atmosphere shader setup
        self._cam_dirty = True

        self._await_setup = asyncio.ensure_future(self._delayed_setup())

    @property
    def usd_stage(self):
        return self._usd_stage

    @property
    def ext_id(self):
        return self._ext_id

    def register_feature_type_delegate(self, feature_type, delegate_type):
        # if our usd stage is not ready yet, we have to postpone the instantiation
        if not self._usd_ready:
            self._feature_type_delegates.append((feature_type, delegate_type))
            return

        feature_type_str = feature_type.feature_type
        if feature_type_str not in self._feature_type_delegates:
            self._feature_type_delegates[feature_type_str] = [delegate_type(self)]
        else:
            self._feature_type_delegates[feature_type_str].append(delegate_type(self))

    def unregister_feature_type_delegate(self, feature_type, delegate_type=None):
        # if our usd stage is not ready yet, the instantiation got postponed
        if not self._usd_ready:
            try:
                self._feature_type_delegates.remove((feature_type, delegate_type))
            except ValueError:
                carb.log_warn(f'Trying to remove not registered delegate: ({feature_type}, {delegate_type})')

        feature_type_str = feature_type.feature_type
        if feature_type_str not in self._feature_type_delegates:
            return
        if not delegate_type:
            del self._feature_type_delegates[feature_type_str]
        else:
            for d in self._feature_type_delegates[feature_type_str]:
                if isinstance(d, delegate_type):
                    self._feature_type_delegates[feature_type_str].remove(d)
                    break

    def _on_time(self, event):
        if event.type in [\
                int(omni.timeline.TimelineEventType.CURRENT_TIME_TICKED_PERMANENT),
                int(omni.timeline.TimelineEventType.CURRENT_TIME_TICKED),
                ]:
            cur_time = self._timeline.get_current_time()
            self._sun_feature_motion.time_changed(self._time_manager.current_utc_time)
            #if self._sun_feature.diurnal_motion or self._sun_feature.seasonal_motion:
            # TODO: for movie capture, we need to support keyframed cameras
            self._cam_dirty = True

    # on_tick event, used for automatic camera orbit
    def _on_tick(self, event):
        # TODO: I suspect that this is too slow going through USD to have a
        # smooth animation. Will need to investigate how to get the usdrt stage
        # handle and update the camera from there
        # NOTE: going through usdrt poses new issues where one needs to synchronize
        # with usd. what if rotation anim is on, writing to fabrics matrices and
        # then a rotation gesture is used? this will overwrite the fabric matrices
        # and thus give a 'jump' in rotation.

        def get_time_delta():
            tick_time = time.time()
            if self._last_tick_time is not None:
                time_delta = tick_time - self._last_tick_time
            else:
                return 0
            # reduce frequency at which we write to USD
            if time_delta is not None and time_delta >= 1/120:
                return time_delta
            else:
                return None

        # avoid lengthy computations if tick rate is higher than our update rate
        if get_time_delta() is None:
            return

        viewport_api = get_active_viewport()
        camera_path = viewport_api.camera_path
        camera = UsdGeom.Camera(self.usd_stage.GetPrimAtPath(camera_path))
        if not camera:
            carb.log_error(f'Viewport API returned invalid camera path: {camera_path}')
        gf_camera = camera.GetCamera(viewport_api.time)

        cam_pos = gf_camera.transform.GetRow(3)
        cam_pos = Gf.Vec3d(cam_pos[0], cam_pos[1], cam_pos[2])
        dist = cam_pos.GetLength()
        cam_dir = cam_pos.GetNormalized()

        phi = np.deg2rad(self._sun_feature.longitude)
        theta = np.deg2rad(90 - self._sun_feature.latitude)

        sun_dir = Gf.Vec3d(
                np.cos(phi)*np.sin(theta),
                np.sin(phi)*np.sin(theta),
                np.cos(theta))

        speed_mag = 1
        if self._sun_feature.active:
            speed_mag *= 1+5*(0.5*(Gf.Dot(-sun_dir, cam_dir)+1))
        # based on camera distance
        dist_fact = max(0.5, np.arctan(1/(dist-self._earth_radius))/np.arctan(1/(20000-self._earth_radius)))
        speed_mag /= dist_fact

        # get time_delta right before update to improve smoothness as much as we can
        time_delta = get_time_delta()
        if time_delta is None:
            return
        self._last_tick_time = time.time()

        rot_matrix = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0,0,1), -speed_mag*time_delta))
        if len(camera.GetOrderedXformOps()) != 1:
            camera.MakeMatrixXform().Set(gf_camera.transform * rot_matrix)
        else:
            camera.GetOrderedXformOps()[0].Set(gf_camera.transform * rot_matrix)

    async def _delayed_setup(self):
        try:
            # TODO: create a usd stage and populate it, don't rely on global ctx
            viewport, self._window = omni.kit.viewport.utility.get_active_viewport_and_window()
            if not self._window:
                return
            self._window.padding_x = 0
            self._window.padding_y = 0
            set_render_settings()

            self._usd_ctx = viewport.usd_context
            if not self._usd_ctx:
                carb.log_warn('No valid USD Context')
                return
            self._usd_stage = self._usd_ctx.get_stage()
            if self._usd_stage is None:
                carb.log_warn('No USD Stage in Viewport')
                return

            # setup base stage
            settings = carb.settings.get_settings()
            tokens = carb.tokens.get_tokens_interface()
            ext_name = omni.ext.get_extension_name(self._ext_id)
            stage_setting = settings.get_as_string(f"/exts/{ext_name}/stage")
            self._stage_path = tokens.resolve(stage_setting)
            self._usd_stage.GetRootLayer().subLayerPaths.append(self._stage_path)
            try:
                UsdGeom.SetStageUpAxis(self._usd_stage, UsdGeom.Tokens.z)
            except:
                # This shouldn't be necessary but the Viewport doesn't handle this correctly
                carb.log_warn('GlobeView had to wait for the Viewport to setup Cameras')
                await omni.kit.app.get_app().next_update_async()
                UsdGeom.SetStageUpAxis(self._usd_stage, UsdGeom.Tokens.z)

            # get the earth's radius:
            globe_xform = UsdGeom.Xform(self._usd_stage.GetPrimAtPath(Sdf.Path('/World/earth_xform/diamond_globe')))
            if globe_xform:
                scale_attr = globe_xform.GetPrim().GetAttribute('xformOp:scale')
                if scale_attr:
                    scale = scale_attr.Get()
                    carb.log_info(f'Setting Earth Radius to: {scale[0]}')
                    self._earth_radius = scale[0]
                    get_geo_converter().sphere_radius = self._earth_radius
                else:
                    carb.log_warn(f'Scale Attribute not found')
            else:
                carb.log_warn(f'Globe Prim Not Found')

            self._usd_ready = True
            # now that we're ready, we need to instantiate all the delegates that
            # got registered but we were not able to add yet
            to_process = self._feature_type_delegates.copy()
            self._feature_type_delegates = {}
            for feature_type, delegate_type in to_process:
                self.register_feature_type_delegate(feature_type, delegate_type)

        except Exception as e:
            carb.log_error(f'Error Setting up USD for GlobeView: {e}')

        # Register 'Factory' GlobeScene with Viewport to ensure this is added to
        # all viewports. I'm not sure if that's really what we want as different
        # viewports might require different Gestures.
        try:
            from omni.kit.viewport.registry import RegisterScene
            self._viewport_registry = RegisterScene(GlobeScene, self._ext_id)
        except ImportError:
            self._viewport_registry = None

        self._screen_ui = GlobeUI(self._ext_id, self._window)

        renderer = omni.kit.renderer.bind.get_renderer_interface()
        self._render_subscription = renderer.get_pre_begin_frame_event_stream().create_subscription_to_pop(self._on_begin_frame)
        self._sun_prim = None
        self._headlight_prim = None
        self._atmos_shader_prim = None

        # NOTE: using this instead of viewport api's view subscription as the viewport api lags behind and thus makes visible artifacts
        self._usd_subscription = Tf.Notice.Register(Usd.Notice.ObjectsChanged, self._on_usd_change, self.usd_stage)

        # register actions and hotkeys
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.register_action(self._ext_id, 'toggle_rotation', self._toggle_rotation, 'Toggle Camera Orbit', 'Toggle automatic Camera Orbit')
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.register_hotkey(self._ext_id, 'R', self._ext_id, 'toggle_rotation')

        # feature type delegate callbacks
        self.register_feature_type_delegate(features_api.Curves, CurvesDelegate)
        self.register_feature_type_delegate(features_api.Image, ImageDelegate)

        self._await_setup = None

    # start/stop automatic camera orbit
    def _toggle_rotation(self):
        carb.log_error('This feature is currently not supported as Kits Perspective Camera does not support additional Xform Ops')
        return

        if not self._tick_event_subscription:
            self._tick_event_subscription = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(self._on_tick)
        else:
            # NOTE: this assumes sole ownership of the subscription
            self._tick_event_subscription.unsubscribe()
            self._tick_event_subscription = None
            self._last_tick_time = None

    # listen to USD events to notice camera changes
    def _on_usd_change(self, notice, stage):
        cam_path = get_active_viewport().camera_path
        for p in notice.GetChangedInfoOnlyPaths():
            if p.GetPrimPath() == cam_path:
                self._cam_dirty = True

    def _on_begin_frame(self, event):
        sun_dirty = self._sun_feature_motion.dirty and self._sun_feature.active
        if not sun_dirty and not self._cam_dirty:
            return

        if sun_dirty:
            self._sun_feature_motion.update(self._time_manager.current_utc_time)
            phi = self._sun_feature.longitude
            theta = 90 - self._sun_feature.latitude

            sun_xform = UsdGeom.Xform(self.usd_stage.GetPrimAtPath('/World/sun'))
            for op in sun_xform.GetOrderedXformOps():
                if op.GetOpType() == UsdGeom.XformOp.TypeRotateXYZ:
                    op.Set(Gf.Vec3d(0, theta, phi))

        # Update Atmosphere Shader and Headlight
        cam_prim = self.usd_stage.GetPrimAtPath(get_active_viewport().get_active_camera())
        if not self._sun_prim:
            self._sun_prim = self.usd_stage.GetPrimAtPath('/World/sun/sun_diffuse')
        if not self._headlight_prim:
            self._headlight_prim = self.usd_stage.GetPrimAtPath('/World/headlight')
        if not self._atmos_shader_prim:
            self._atmos_shader_prim = self.usd_stage.GetPrimAtPath('/World/Looks/AtmospherePrecomputed/Shader')

        if not cam_prim or not self._sun_prim or not self._headlight_prim or not self._atmos_shader_prim:
            carb.log_error(f'error getting prims for globe view shader update:\n\tcam: {cam_prim}, sun: {self._sun_prim}, headlight: {self._headlight_prim}, atmos shader: {self._atmos_shader_prim}')
            return

        # set cam an sun pos in shader
        xform_cache = UsdGeom.XformCache(self._timeline.get_current_time()*self._timeline.get_time_codes_per_seconds())
        cam_pos = xform_cache.GetLocalToWorldTransform(cam_prim).ExtractTranslation()
        light_orientation = xform_cache.GetLocalToWorldTransform(self._sun_prim).GetRow(2)
        self._atmos_shader_prim.GetAttribute('inputs:cam_pos').Set(cam_pos)
        vec = Gf.Vec3f(light_orientation[0], light_orientation[1], light_orientation[2]).GetNormalized()
        self._atmos_shader_prim.GetAttribute('inputs:sun_dir').Set(vec)

        self._cam_dirty = False

        # update headlight
        cam_xform = xform_cache.GetLocalToWorldTransform(cam_prim)
        UsdGeom.Xformable(self._headlight_prim).MakeMatrixXform().Set(cam_xform)

    # callback when a feature has been changed
    def _on_feature_change(self, event):
        change = event.payload['change']
        feature_type = event.payload['feature_type']

        # the Clear event should remove all features. not used and
        # TODO: we should probably remove it
        # NOTE: it might be useful when a E2CC instance needs to switch between
        # different states
        if change['id'] == features_api.FeatureChange.FEATURE_CLEAR['id']:
            self._sun_feature = None
            self._sun_feature_motion = None
            self._headlight_feature = None
            self._ambient_light_feature = None
            self._atmos_feature = None
            # call feature type delegates
            for type_name, delegates in self._feature_type_delegates.items():
                for d in delegates:
                    d(event, self)

        # the reorder event comes frome the feature api itself (so sender 0).
        # this is why we we let it be handled by every delegate
        elif change['id'] == features_api.FeatureChange.FEATURE_REORDER['id']:
            # call feature type delegates
            for type_name, delegates in self._feature_type_delegates.items():
                for d in delegates:
                    d(event, self)

        elif feature_type == 'Light' or feature_type == 'Sun':
            if event.sender == self._atmos_feature.id:
                self._handle_atmos_event(event)
            else:
                self._handle_light_event(event)

        # call feature type delegates
        if feature_type in self._feature_type_delegates:
            for d in self._feature_type_delegates[feature_type]:
                d(event, self)

    def _handle_light_event(self, event):
        light_features = [self._sun_feature, self._headlight_feature, self._ambient_light_feature]

        cur_feature = None
        for f in light_features:
            if f.id == event.sender:
                cur_feature = f
        if cur_feature is None:
            return False

        change = event.payload['change']
        if change['id'] == features_api.FeatureChange.FEATURE_REMOVE['id']:
            cur_feature = None
            return True

        if change['id'] == features_api.FeatureChange.PROPERTY_CHANGE['id']:
            if event.payload['property'] == 'active':
                new_value = event.payload['new_value']
                if cur_feature == self._sun_feature:
                    self._toggle_sun(new_value)
                elif cur_feature == self._headlight_feature:
                    self._toggle_headlight(new_value)
                elif cur_feature == self._ambient_light_feature:
                    self._toggle_ambient_light(new_value)
                return True
            elif cur_feature == self._sun_feature:
                self._sun_feature_motion.feature_property_changed()
        return True

    def _handle_atmos_event(self, event):
        change = event.payload['change']

        if change['id'] == features_api.FeatureChange.FEATURE_REMOVE['id']:
            self._atmos_feature = None
            return True

        if change['id'] == features_api.FeatureChange.PROPERTY_CHANGE['id']:
            if event.payload['property'] == 'active':
                new_value = event.payload['new_value']
                self._toggle_atmos(new_value)
                return True
        return True

    # toggle sun visibility
    def _toggle_sun(self, value=None):
        if value is None:
            value = not self._sun_feature.active

        toggle_visibility(self.usd_stage, '/World/sun', value)
        self._headlight_feature.active = value
        self._atmos_feature.active = value
        self._ambient_light_feature.active = not value

    # toggle headlight visibility
    def _toggle_headlight(self, value=None):
        if value is None:
            value = not self._headlight_feature.active
        toggle_visibility(self.usd_stage, '/World/headlight', value)

    # toggle ambient light visibility
    def _toggle_ambient_light(self, value=None):
        if value is None:
            value = not self._ambient_light_feature.active

        self._ambient_light_feature.active = value
        self._sun_feature.active = not value
        self._headlight_feature.active = not value
        self._atmos_feature.active = not value
        settings = carb.settings.get_settings()
        if value == True:
            settings.set("/rtx/sceneDb/ambientLightColor", (1,1,1))
            settings.set_float("/rtx/sceneDb/ambientLightIntensity", 0.5)
        else:
            settings.set_float("/rtx/sceneDb/ambientLightIntensity", 0.0)

    # toggle atmosphere visibility
    def _toggle_atmos(self, value=None):
        if value is None:
            value = not self._atmos_feature.active

        toggle_visibility(self.usd_stage, '/World/earth_xform/atmos', value)
        if value:
            self._sun_feature.active = value

    # when FeatureProperties exention gets loaded, we enable more features
    def _on_feature_properties_enable(self, ext_id:str):
        # register to feature properties ui
        self._register_add_callback('Add Sun', self._add_sun_feature)
        self._register_add_callback('Add Headlight', self._add_headlight_feature)
        self._register_add_callback('Add Ambient Light', self._add_ambient_light_feature)

    def _add_sun_feature(self):
        if self._sun_feature is not None:
            carb.log_warn('Sun Feature already present')
            return
        self._sun_feature = self._features_api.create_sun_feature()
        self._sun_feature.name = 'Sun'
        self._sun_feature_motion = sun_motion.SunMotion(self._sun_feature)
        self._features_api.add_feature(self._sun_feature)

    def _add_headlight_feature(self):
        if self._headlight_feature is not None:
            carb.log_warn('Headlight Feature already present')
            return
        self._headlight_feature = self._features_api.create_light_feature()
        self._headlight_feature.name = 'Headlight'
        self._features_api.add_feature(self._headlight_feature)

    def _add_ambient_light_feature(self):
        if self._ambient_light_feature is not None:
            carb.log_warn('Ambient Light Feature already present')
            return
        self._ambient_light_feature = self._features_api.create_light_feature()
        self._ambient_light_feature.active = False
        self._ambient_light_feature.name = 'Ambient Light'
        self._features_api.add_feature(self._ambient_light_feature)

    def _add_atmos_feature(self):
        if self._atmos_feature is not None:
            carb.log_warn('Atmos Feature already present')
            return
        self._atmos_feature = self._features_api.create_light_feature()
        self._atmos_feature.name = 'Atmosphere'
        self._features_api.add_feature(self._atmos_feature)

    def _register_add_callback(self, name, callback):
        from omni.earth_2_command_center.app.window.feature_properties import get_instance
        feature_properties = get_instance()
        feature_properties.register_feature_type_add_callback(name, callback)
        self._registered_names.append(name)

    def _on_feature_properties_disable(self, ext_id:str):
        self._unregister_add_callbacks()

    def _is_feature_properties_enabled(self):
        # get the extension manager
        ext_manager = omni.kit.app.get_app_interface().get_extension_manager()
        feature_properties_ext_name = 'omni.earth_2_command_center.app.window.feature_properties'
        return ext_manager.is_extension_enabled(feature_properties_ext_name)

    def _unregister_add_callbacks(self):
        if not self._is_feature_properties_enabled():
            return

        from omni.earth_2_command_center.app.window.feature_properties import get_instance
        feature_properties = get_instance()
        for name in self._registered_names:
            feature_properties.unregister_feature_type_add_callback(name)
        self._registered_names = []

    def on_shutdown(self):
        hotkey_registry = omni.kit.hotkeys.core.get_hotkey_registry()
        hotkey_registry.deregister_all_hotkeys_for_extension(self._ext_id)
        action_registry = omni.kit.actions.core.acquire_action_registry()
        action_registry.deregister_all_actions_for_extension(self._ext_id)

        self._unregister_add_callbacks()

        if self._tick_event_subscription is not None:
            self._tick_event_subscription.unsubscribe()
            self._tick_event_subscription = None

        self._usd_subscription.Revoke()

        #self._window = None
        if self._feature_subscription:
            self._feature_subscription.unsubscribe()
        if self._timeline_subscription:
            self._timeline_subscription.unsubscribe()

        # remove light features
        for f in [self._sun_feature, self._headlight_feature, self._ambient_light_feature, self._atmos_feature]:
            if f is not None:
                self._features_api.remove_feature(f)
                f = None
        self._sun_feature_motion = None

        if self._screen_ui:
            self._screen_ui.unload()
            self._screen_ui = None

        #self._usd_ctx.new_stage()

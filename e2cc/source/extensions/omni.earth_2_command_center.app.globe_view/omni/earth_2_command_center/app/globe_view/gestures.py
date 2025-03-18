# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [
    "BINDINGS",
    "CameraGestureManager",
    "GlobeGestureContainer"
]

from typing import Callable, List, Optional

import carb

import carb.input
from carb.settings import get_settings

from pxr import Gf

import omni.ui.scene as sc

from omni.kit.manipulator.camera.gestures import TumbleGesture, ZoomGesture

from omni.kit.viewport.utility import get_active_viewport_camera_path, get_active_viewport
from omni.kit.viewport.utility.camera_state import ViewportCameraState

from omni.earth_2_command_center.app.geo_utils import get_geo_converter

from .reference_manager import ReferenceManager

BINDINGS = {
    "GlobeTumbleGesture": "LeftButton",
    "GlobeZoomGesture": "RightButton"
}

class CameraGestureManager(sc.GestureManager):
    """
        Prevent unnecessary gestures
    """
    def __init__(self):
        super().__init__()

    def can_be_prevented(self, arg0) -> bool:
        return False if arg0.name == "GlobeZoomGesture" else True

    def should_prevent(self, arg0, arg1) -> bool:
        # Block the base camera manipulator LookGesture in favor for Zoom
        if arg0.name in ["PanGesture", "LookGesture", "TumbleGesture", "ZoomGesture"]:
            return True

        if arg0.name == "GlobeTumbleGesture" and arg1.name == "GlobeZoomGesture" and arg1.state != sc.GestureState.POSSIBLE:
            return True
        return super().should_prevent(arg0, arg1)


class GlobeZoomGesture(ZoomGesture):
    def __init__(self, model, configure_model, mouse_button: int, modifiers: int, manager=None):
        super().__init__(model, configure_model, mouse_button=mouse_button, modifiers=modifiers, manager=manager)

        settings = get_settings()
        self.__zoom_min = settings.get_as_int("/exts/omni.earth_2_command_center.app.globe_view/zoom_min")
        self.__zoom_max = settings.get_as_int("/exts/omni.earth_2_command_center.app.globe_view/zoom_max")
        self._earth_radius = get_geo_converter().sphere_radius

    def on_mouse_move(self, mouse_moved):
        """
            Reimplementation of the base mouse move to handle for min/max
        """
        if self.disable_zoom:
            return

        import numpy as np
        amount = -(mouse_moved[0] + mouse_moved[1]) #  dot product with camera's negative x-axis and negative y-axis

        camera_path = get_active_viewport_camera_path()
        cam_state = ViewportCameraState(camera_path)
        cam_pos = cam_state.position_world
        cam_dist = (cam_pos).GetLength()
        dir_norm = cam_pos.GetNormalized()

        # Zoom into Origin
        direction = (-cam_pos).GetNormalized()
        amount = np.clip(amount,-10,10) * np.clip(cam_dist-self._earth_radius, 1e-6, 100000) * self.move_speed[2] * 3

        ## compute camera position and new position along forward vector
        ## Limit the position if calculated is not between the min/max.
        #new_pos = cam_pos + (dir_norm * amount)
        #new_dist = (new_pos).GetLength()
        #if not self.__zoom_max > new_dist > self.__zoom_min:
        #    return
        amount = np.clip(amount, self.__zoom_min-cam_dist, self.__zoom_max-cam_dist)

        self._accumulate_values('move', 0, 0, amount)


# Rename for global scope
class GlobeTumbleGesture(TumbleGesture):
    def on_mouse_move(self, mouse_moved):
        viewport = get_active_viewport()
        res = viewport.resolution
        aspect = res[0]/res[1]

        camera_path = get_active_viewport_camera_path()
        cam_state = ViewportCameraState(camera_path)
        cam_pos = cam_state.position_world
        cam_dist = (cam_pos).GetLength()

        earth_radius = get_geo_converter().sphere_radius
        import numpy as np
        scale = np.clip(0.00004/np.arctan(1/
                np.clip(cam_dist-earth_radius,1,30000)), 1e-8, 3)
        mouse_moved = (
                mouse_moved[0]*aspect*scale,
                mouse_moved[1]*scale)

        #carb.log_warn(f'Cam Dist: {cam_dist}, mouse_moved: {mouse_moved}')

        # Mouse moved is [-1,1], so make a full drag scross the viewport a 180 tumble
        speed = self.tumble_speed
        self._accumulate_values('tumble', mouse_moved[0] * speed[0] * -90,
                                          mouse_moved[1] * speed[1] * 90,
                                          0)

class GlobeGestureContainer:
    def __init__(
        self,
        model: sc.AbstractManipulatorModel,
        bindings: Optional[dict] = None,
        manager: Optional[sc.GestureManager] = None,
        configure_model: Optional[Callable] = None
    ):
        from omni.kit.manipulator.camera.gestures import build_gestures
        # TODO: I'm not proud of this but I have to add it this way to be able
        # to reuse the build_gestures code
        build_gestures.__globals__['GlobeTumbleGesture'] = GlobeTumbleGesture
        build_gestures.__globals__['GlobeZoomGesture'] = GlobeZoomGesture
        self._gestures = build_gestures(model, bindings, manager, configure_model)

    @property
    def tumble(self) -> Optional[GlobeTumbleGesture]:
        return self._gestures.get("GlobeTumbleGesture", None)

    @property
    def zoom(self) -> Optional[GlobeZoomGesture]:
        return self._gestures.get("GlobeZoomGesture", None)

    @property
    def gestures(self) -> List:
        #return list(self._gestures.values())
        return self._gestures

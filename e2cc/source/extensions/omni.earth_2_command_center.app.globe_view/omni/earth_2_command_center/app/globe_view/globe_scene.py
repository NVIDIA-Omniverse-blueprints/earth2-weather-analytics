# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import time
from typing import cast

from carb import log_error
from carb.settings import get_settings

from omni.kit.manipulator.camera.viewport_camera_manipulator import ViewportCameraManipulator
from omni.kit.manipulator.camera.model import CameraManipulatorModel
from omni.kit.viewport.window.events import set_ui_delegate

import omni.ui.scene as sc

from .gestures import (
    BINDINGS,
    #build_gestures,
    CameraGestureManager,
    GlobeGestureContainer
)

from .reference_manager import ReferenceManager

class GlobeScene:
    """
        Globe Window with Manipulator
    """
    def __init__(self, vp_args: dict):
        self.__settings = get_settings()
        self._viewport_api = vp_args["viewport_api"]
        self.visible = True  # Required

        self._camera_manipulator = ViewportCameraManipulator(
            self._viewport_api,
        )
        manager = CameraGestureManager()
        self._camera_manipulator.manager = manager
        #self._camera_manipulator.visible = True

        model = self._camera_manipulator.model
        model.set_ints("disable_look", [1])
        model.set_ints("disable_pan", [1])
        model.set_ints("disable_fly", [1])

        # Camera Inertia
        model.set_ints("inertia_enabled", [self.__settings.get_as_int("/persistent/app/viewport/camInertiaEnabled")])
        model.set_ints("inertia_decay", [self.__settings.get_as_int("/persistent/exts/omni.kit.manipulator.camera/inertiaDecay")])
        model.set_floats("inertia_seconds", [0.5])
        model.set_ints("tumble_acceleration", [400, 400, 400])
        model.set_ints("tumble_dampening", [10, 10, 10])
        model.set_ints("move_acceleration", [100, 100, 100])
        model.set_ints("move_dampening", [1, 1, 1])

        self.__gesture_container = GlobeGestureContainer(
            model,
            BINDINGS,#self._camera_manipulator.bindings,
            manager,
            self._camera_manipulator._on_began
        )

        with sc.Transform():
            self._screen = sc.Screen(gestures=self.__gesture_container.gestures)

        # Set scene in ref manager for access
        ReferenceManager().globe_scene = self

# XXX: set ui delegate to None to prevent mouse wheel to zoom
set_ui_delegate(None)

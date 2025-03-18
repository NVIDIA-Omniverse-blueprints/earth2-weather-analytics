# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# import omni.earth_2_command_center.app.globe_view.globe_scene as globe_scene
# import omni.earth_2_command_center.app.globe_view.globe_ui as globe_ui
# import omni.earth_2_command_center.app.globe_view.reference_manager as reference_manager

import omni.kit.test
#import datetime

class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        '''No need for setup work'''

    async def tearDown(self):
        '''No need for teardown work'''

    # ============================================================
    # Globe View Tests
    # ============================================================
    #async def test_globe_view_window(self):
    #    window = globe_view.Earth2GlobeView()
    #    self.assertIsNotNone(window)
    #    del window

    #async def test_globe_view_viewport_api(self):
    #    window = globe_view.Earth2GlobeView()
    #    viewport_api = window.viewport_api
    #    self.assertIsNotNone(viewport_api)
    #    del window

    #async def test_globe_view_scene_view(self):
    #    window = globe_view.Earth2GlobeView()
    #    scene_view = window.scene_view
    #    self.assertIsNotNone(scene_view)
    #    del window

    #async def test_globe_view_set_style(self):
    #    window = globe_view.Earth2GlobeView()
    #    window.set_style({'background_color': 0x0})
    #    del window

    # ============================================================
    # Reference Manager Tests
    # ============================================================
    #async def test_reference_manager(self):
    #    ref_man = reference_manager.ReferenceManager()
    #    self.assertIsNotNone(ref_man)

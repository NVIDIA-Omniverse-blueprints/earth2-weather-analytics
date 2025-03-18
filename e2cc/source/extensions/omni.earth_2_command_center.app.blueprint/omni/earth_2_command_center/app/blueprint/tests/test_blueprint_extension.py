# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import omni.kit.test

import json

import omni.earth_2_command_center.app.blueprint.api as api
import omni.earth_2_command_center.app.core as core
from omni.earth_2_command_center.app.core.features_api import (
    Feature,
    Image,
    Curves,
    Light,
    Sun,
)


class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        """No need for setup work"""
        # TODO: do we neet to call api.initialize?

    async def tearDown(self):
        """No need for teardown work"""

    # ============================================================
    # Core Tests
    # ============================================================
    async def test_fetch(self):
        # TODO: can't really test it yet
        pass

    async def test_set_layer_order(self):
        # TODO: can't really test it yet
        pass

    async def test_set_layer_visibility_empty(self):
        # test that this doesn't throw
        api.post_set_layer_visibility(None, False)

    async def test_set_layer_visibility(self):
        features_api = core.get_state().get_features_api()
        feature = features_api.create_feature(Feature)
        feature.active = True
        feature.name = "Test Feature"
        features_api.add_feature(feature)

        api.post_set_layer_visibility(feature.id, False)
        self.assertEqual(feature.active, False)
        api.post_set_layer_visibility(feature.id, True)
        self.assertEqual(feature.active, True)

        features_api.remove_feature(feature)

    async def test_set_lead_time(self):
        # TODO: can't really test it yet
        pass

    async def test_sun_light(self):
        features_api = core.get_state().get_features_api()
        feature = features_api.create_feature(Sun)
        feature.active = True
        feature.name = "Sun"
        features_api.add_feature(feature)

        api.post_sun_light(False)
        self.assertEqual(feature.active, False)
        api.post_sun_light(True)
        self.assertEqual(feature.active, True)

        features_api.remove_feature(feature)

    async def test_atmosphere(self):
        features_api = core.get_state().get_features_api()
        feature = features_api.create_light_feature()
        feature.active = True
        feature.name = "Atmosphere"
        features_api.add_feature(feature)

        api.post_atmosphere(False)
        self.assertEqual(feature.active, False)
        api.post_atmosphere(True)
        self.assertEqual(feature.active, True)

        features_api.remove_feature(feature)

    async def test_stars(self):
        pass

    async def test_topography(self):
        # TODO: can't really test it yet
        pass

    async def test_coastlines(self):
        features_api = core.get_state().get_features_api()
        feature = features_api.create_curves_feature()
        feature.active = True
        feature.name = "Continents Outline"
        features_api.add_feature(feature)

        api.post_coastlines(False)
        self.assertEqual(feature.active, False)
        api.post_coastlines(True)
        self.assertEqual(feature.active, True)

        features_api.remove_feature(feature)

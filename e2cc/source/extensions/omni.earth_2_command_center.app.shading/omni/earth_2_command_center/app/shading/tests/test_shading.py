# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import omni.earth_2_command_center.app.core as core
import omni.earth_2_command_center.app.shading as shading
from omni.earth_2_command_center.app.shading.shader_library import ShaderSpec

import omni.kit.test
import omni.usd

from pxr import Usd, UsdShade, Sdf, Gf

import os

class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        '''No need for setup work''' 

    async def tearDown(self):
        '''No need for teardown work''' 

    # ============================================================
    # Core Tests
    # ============================================================
    async def test_get_shader_library(self):
        self.assertIsNotNone(shading.get_shader_library())

    async def test_get_shaders(self):
        shader_library = shading.get_shader_library()
        shaders = shader_library.get_shaders()
        self.assertIsNotNone(shaders)
        self.assertTrue(len(shaders) > 0)

    async def test_get_shader_spec(self):
        shader_library = shading.get_shader_library()
        shaders = shader_library.get_shaders()

        for shader_name,shader_spec in shaders.items():
            spec = shader_library.get_shader_spec(shader_name)
            self.assertIsNotNone(spec)
            self.assertEqual(spec, shader_spec)

    async def test_get_shader_spec_invalid(self):
        shader_library = shading.get_shader_library()
        self.assertIsNone(shader_library.get_shader_spec('invalid_shader'))

    async def test_get_shader_path(self):
        shader_library = shading.get_shader_library()
        path = shader_library.get_shader_path('layering')
        self.assertTrue(os.path.exists(path))

    async def test_get_colormap_path(self):
        shader_library = shading.get_shader_library()
        path = shader_library.get_colormap_path('viridis')
        self.assertTrue(os.path.exists(path))

    async def test_add_shader(self):
        shader_library = shading.get_shader_library()

        spec = ShaderSpec('test_shader', 'test_path', 'sub_identifier')
        shader_library.add_shader('test_shader', spec)

        shaders = shader_library.get_shaders()
        self.assertTrue('test_shader' in shaders)
        self.assertEqual(shaders['test_shader'], spec)

    # ============================================================
    # Network Tests
    # ============================================================
    async def test_create_shader_prim(self):
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()

        shader_library = shading.get_shader_library()
        spec = shader_library.get_shader_spec('merge')
        prim = shading.create_shader_prim(stage, Sdf.Path('/Looks/merge_test'), spec)

        self.assertTrue(prim)

    async def test_create_material_prim(self):
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()

        shader_library = shading.get_shader_library()
        spec = shader_library.get_shader_spec('LayeredMaterial')
        material_prim, shader_prim = shading.create_material_prim(stage, Sdf.Path('/Looks/material'), spec)

        self.assertTrue(material_prim.GetPrim().IsValid())
        self.assertTrue(shader_prim.GetPrim().IsValid())

    async def test_create_layered_shell_material(self):
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()

        test_prim = stage.DefinePrim('/prim')
        shader_library = shading.get_shader_library()
        material_prim, update_mapping = shading.create_layered_shell_material(stage, bind_path=test_prim.GetPath())
        self.assertTrue(material_prim.GetPrim().IsValid())

    async def test_create_layered_shell_material_layered(self):
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()

        features_api = core.get_state().get_features_api()

        # create dummy latlong feature
        feature = features_api.create_image_feature()
        feature.projection = 'latlong'
        feature.longitudinal_offset = 20
        feature.sources = ['dummy.jpg']
        feature.alpha_sources = ['dummy.jpg']
        features_api.add_feature(feature)

        # create dummy diamond feature
        feature = features_api.create_image_feature()
        feature.projection = 'diamond'
        feature.sources = ['dummy.jpg']*10
        feature.alpha_sources = ['dummy.jpg']*10
        features_api.add_feature(feature)
        
        test_prim = stage.DefinePrim('/prim')
        shader_library = shading.get_shader_library()
        material_prim, update_mapping = shading.create_layered_shell_material(
                stage, 
                bind_path = test_prim.GetPath(),
                features = features_api.get_image_features())
        self.assertTrue(material_prim.GetPrim().IsValid())

        features_api.clear()

    async def test_create_layered_shell_material_layered_invalid_sources(self):
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()

        features_api = core.get_state().get_features_api()
        def test(feature):
            with self.assertRaises(ValueError):
                test_prim = stage.DefinePrim('/prim')
                shader_library = shading.get_shader_library()
                material_prim, update_mapping = shading.create_layered_shell_material(
                        stage, 
                        bind_path = test_prim.GetPath(),
                        features = [feature])

        # create dummy feature with invalid projection
        feature = features_api.create_image_feature()
        feature.projection = 'invalid'
        feature.sources = ['foo.jpg']
        test(feature)

        # create dummy feature with invalid projection
        feature = features_api.create_image_feature()
        feature.projection = 'invalid'
        feature.alpha_sources = ['foo.jpg']
        test(feature)

        # create diamond feature with too few sources
        feature = features_api.create_image_feature()
        feature.projection = 'diamond'
        feature.sources = ['foo.jpg']*9
        test(feature)

        # create diamond feature with too few alpha_sources
        feature = features_api.create_image_feature()
        feature.projection = 'diamond'
        feature.alpha_sources = ['foo.jpg']*9
        test(feature)


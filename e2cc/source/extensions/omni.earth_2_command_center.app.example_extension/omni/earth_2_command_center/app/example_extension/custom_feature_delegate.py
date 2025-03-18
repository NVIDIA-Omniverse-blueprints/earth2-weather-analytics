# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['CustomFeatureDelegate']

import carb

from pxr import UsdGeom, UsdShade, Gf

from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features_api as features_api_module
from omni.earth_2_command_center.app.geo_utils import get_geo_converter
from omni.earth_2_command_center.app.globe_view.utils import create_unique_prim_path, toggle_visibility
from omni.earth_2_command_center.app.shading import get_shader_library, create_material_prim

from .custom_feature import CustomFeature

class CustomFeatureDelegate:
    def __init__(self, viewport):
        self._viewport = viewport
        self._managed_features = {}
        # TODO: check already existing features and add when required
        self._representations = {}
        features = get_state().get_features_api().get_by_type(CustomFeature)
        for f in features:
            self._add_feature_representation(f.id)

    def __del__(self):
        to_remove = list(self._representations.keys())
        for feature_id in to_remove:
            self._remove_feature_representation(feature_id)

    def __call__(self, event, globe_view):
        change = event.payload['change']
        usd_stage = globe_view.usd_stage

        feature_id = event.sender

        # handle events
        if feature_id not in self._representations or change['id'] == features_api_module.FeatureChange.FEATURE_ADD['id']:
            self._add_feature_representation(feature_id)

        if change['id'] == features_api_module.FeatureChange.FEATURE_REMOVE['id']:
            self._remove_feature_representation(feature_id)

        elif change['id'] == features_api_module.FeatureChange.FEATURE_CLEAR['id']:
            for r in self._representations:
                self._viewport.usd_stage.RemovePrim(r['prim_path'])
            self._representations = {}

        elif change['id'] == features_api_module.FeatureChange.PROPERTY_CHANGE['id']:
            carb.log_warn('handling property change')
            feature = get_state().get_features_api().get_feature_by_id(feature_id)

            if event.payload['property'] == 'active':
                toggle_visibility(self._viewport.usd_stage,
                                  self._representations[feature_id]['prim_path'],
                                  event.payload['new_value'])

            elif event.payload['property'] in ['latitude', 'longitude', 'altitude']:
                prim_path = self._representations[feature_id]['prim_path']
                lon, lat, alt = (feature.longitude, feature.latitude, feature.altitude)
                x,y,z = get_geo_converter().lonlatalt_to_xyz(lon, lat, alt)
                UsdGeom.XformCommonAPI(usd_stage.GetPrimAtPath(prim_path)).SetTranslate(Gf.Vec3d(x,y,z))

            elif event.payload['property'] == 'color':
                prim_path = self._representations[feature_id]['shader_path']
                shader = UsdShade.Shader(usd_stage.GetPrimAtPath(prim_path))
                shader.GetInput('emission_color').Set(feature.color)

    def _add_feature_representation(self, feature_id):
        if feature_id in self._representations:
            return
        carb.log_warn('adding custom feature')

        usd_stage = self._viewport.usd_stage
        path = create_unique_prim_path(prefix='custom_feature')
        sphere = UsdGeom.Sphere.Define(usd_stage, path)
        sphere.GetRadiusAttr().Set(50)

        shader_spec = get_shader_library().get_shader_spec('BasicMaterial')
        mtl_path = path.AppendChild(f'material')
        material_prim, shader_prim = create_material_prim(usd_stage,
                mtl_path,
                shader_spec)

        # get feature
        feature = get_state().get_features_api().get_feature_by_id(feature_id)
        # setup shader
        shader = UsdShade.Shader(shader_prim)
        shader.GetInput('emission_intensity').Set(10000)
        shader.GetInput('emission_color').Set(feature.color)
        sphere.GetPrim().ApplyAPI(UsdShade.MaterialBindingAPI)
        UsdShade.MaterialBindingAPI(sphere.GetPrim()).Bind(material_prim)

        # setup transform
        lon, lat, alt = (feature.longitude, feature.latitude, feature.altitude)
        x,y,z = get_geo_converter().lonlatalt_to_xyz(lon, lat, alt)
        UsdGeom.XformCommonAPI(sphere.GetPrim()).SetTranslate(Gf.Vec3d(x,y,z))

        self._representations[feature_id] = {'prim_path':path, 'material_path':material_prim.GetPath(), 'shader_path':
                                             shader_prim.GetPath()}

    def _remove_feature_representation(self, feature_id):
        if feature_id not in self._representations:
            return
        carb.log_warn('removing custom feature')
        prim_path = self._representations[feature_id]['prim_path']
        carb.log_warn(f'prim path: {prim_path}')
        self._viewport.usd_stage.RemovePrim(prim_path)
        del self._representations[feature_id]


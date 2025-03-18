# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['CurvesDelegate']

import numpy as np

from pxr import UsdGeom, UsdShade, Sdf, Tf, Usd, Gf

import omni.usd

from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features_api as features_api
from omni.earth_2_command_center.app.geo_utils import get_geo_converter
from omni.earth_2_command_center.app.shading import get_shader_library, create_material_prim

from .utils import *

class CurvesDelegate:
    def __init__(self, viewport):
        self._features_info = {}
        # TODO: check already existing features and add when required

    def __call__(self, event, globe_view):
        change = event.payload['change']
        usd_stage = globe_view.usd_stage

        # handle clear event
        if change['id'] in [
                features_api.FeatureChange.FEATURE_CLEAR['id'],
                ]:
            for id in self._features_info:
                usd_stage.RemovePrim(self._features_info[id]['prim_path'])
            self._features_info = {}
            return

        # handle reorder event
        elif change['id'] in [
                features_api.FeatureChange.FEATURE_REORDER['id'],
                ]:
            # we don't need to handle that
            return

        id = event.sender
        feature = get_state().get_features_api().get_feature_by_id(id)

        def update_shader_color(feature_info):
            curves = UsdGeom.BasisCurves(usd_stage.GetPrimAtPath(feature_info['prim_path']))
            num_curves = curves.GetCurveCount()

            shader = UsdShade.Shader(usd_stage.GetPrimAtPath(feature_info['shader_prim_path']))
            if feature.color is None:
                shader.GetInput('emission_intensity').Set(0)
                shader.GetInput('emission_color_primvar').Set('')
                return

            # simple case of constant color
            if len(feature.color) == 3:
                shader.GetInput('emission_color').Set(feature.color)
                shader.GetInput('emission_color_primvar').Set('')
            # else we have to use the displayColor primvar
            else:
                shader.GetInput('emission_color').Set(Gf.Vec3f(1,1,1))
                shader.GetInput('emission_color_primvar').Set('displayColor')
                displayColor = curves.GetDisplayColorPrimvar()
                # if it uniform (per curve)?
                if len(feature.color) == num_curves:
                    displayColor.SetInterpolation(UsdGeom.Tokens.uniform)
                # else we assume per vertex
                else:
                    displayColor.SetInterpolation(UsdGeom.Tokens.vertex)
                displayColor.Set(Vt.Vec3fArray.FromNumpy(np.array(feature.color, dtype=np.float32)))

        feature_info = None
        if id not in self._features_info:
            # not tracked yet, create a prim for it
            # Create Geometry
            path = create_unique_prim_path(prefix='curves')
            prim = UsdGeom.BasisCurves.Define(usd_stage, path)
            prim.GetTypeAttr().Set(UsdGeom.Tokens.linear)
            prim.GetBasisAttr().Set(UsdGeom.Tokens.bspline)
            toggle_visibility(usd_stage, path, feature.active)

            if feature.periodic:
                prim.GetWrapAttr().Set(UsdGeom.Tokens.periodic)
            else:
                prim.GetWrapAttr().Set(UsdGeom.Tokens.nonperiodic)
            if feature.points is not None:
                if feature.projection is None or str(feature.projection).lower() == 'raw':
                    prim.GetPointsAttr().Set(feature.points)
                else:
                    # points need projection
                    # TODO: provide these tools in the core
                    if feature.projection.lower() in ['latlon', 'latlong', 'latlonalt', 'latlongalt']:
                        num_points = len(feature.points)
                        proj_points = np.ndarray((num_points, 3))

                        has_altitude = feature.projection.lower() in ['latlonalt', 'latlongalt'] and feature.points.shape[1] >= 3

                        geo_converter = get_geo_converter()
                        x,y,z = geo_converter.lonlatalt_to_xyz(
                                feature.points[:,1],
                                feature.points[:,0],
                                feature.points[:,2] if has_altitude else 1)
                        proj_points[:,0] = x
                        proj_points[:,1] = y
                        proj_points[:,2] = z
                    else:
                        raise RuntimeError(f'Unsupported projection: {feature.projection}')
                    prim.GetPointsAttr().Set(proj_points)

            if feature.points_per_curve is not None:
                prim.GetCurveVertexCountsAttr().Set(feature.points_per_curve)
            if feature.width is not None:
                prim.SetWidthsInterpolation(UsdGeom.Tokens.constant)
                prim.GetWidthsAttr().Set([feature.width])

            # Create Material
            mtl_path = prim.GetPath().AppendChild('Material')
            stage = omni.usd.get_context().get_stage()
            if not stage.GetPrimAtPath(mtl_path):
                layered_material_spec = get_shader_library().get_shader_spec('BasicMaterial')
                material_prim, basic_shader_prim = create_material_prim(stage,
                        mtl_path,
                        layered_material_spec)
            else:
                material_prim = UsdShade.Material(stage.GetPrimAtPath(mtl_path))
                basic_shader_prim = stage.GetPrimAtPath(mtl_path.AppendChild('Shader'))

            shader = UsdShade.Shader(basic_shader_prim)
            shader.GetInput('emission_intensity').Set(10000)
            shader.GetInput('emission_color').Set(feature.color)

            bind_prim = stage.GetPrimAtPath(prim.GetPath())
            if bind_prim and not bind_prim.HasAPI(UsdShade.MaterialBindingAPI):
                bind_prim.ApplyAPI(UsdShade.MaterialBindingAPI)
            if bind_prim:
                UsdShade.MaterialBindingAPI(bind_prim).Bind(material_prim)

            feature_info = {
                    'prim':prim,
                    'prim_path':prim.GetPath(),
                    'shader_prim_path':shader.GetPath()}
            self._features_info[id] = feature_info

            update_shader_color(feature_info)
        else:
            feature_info = self._features_info[id]

        # new curves feature
        if change['id'] == features_api.FeatureChange.FEATURE_ADD['id']:
            # already handled
            pass

        # curve feature was deleted
        elif change['id'] == features_api.FeatureChange.FEATURE_REMOVE['id']:
            if id in self._features_info:
                usd_stage.RemovePrim(self._features_info[id]['prim_path'])
                del self._features_info[id]

        # handle property changes
        elif change['id'] == features_api.FeatureChange.PROPERTY_CHANGE['id']:
            property_name = event.payload['property']
            curves_prim = feature_info['prim']

            if property_name == 'active':
                toggle_visibility(usd_stage, feature_info['prim_path'], event.payload['new_value'])

            elif property_name == 'points':
                curves_prim = feature_info['prim']
                if feature.points is not None:
                    curves_prim.GetPointsAttr().Set(feature.points)

            elif property_name == 'points_per_curve':
                curves_prim = feature_info['prim']
                if feature.points_per_curve is not None:
                    curves_prim.GetCurveVertexCountsAttr().Set(feature.points_per_curve)

            # TODO: handle different ways to set width: constant, per curve, per vertex
            elif property_name == 'width':
                curves_prim = feature_info['prim']
                if feature.points_per_curve is not None:
                    curves_prim.GetWidthsAttr().Set([feature.width])

            elif property_name == 'periodic':
                if feature.periodic:
                    prim.GetWrapAttr().Set(UsdGeom.Tokens.periodic)
                else:
                    prim.GetWrapAttr().Set(UsdGeom.Tokens.nonperiodic)

            elif property_name == 'color':
                shader = UsdShade.Shader(usd_stage.GetPrimAtPath(feature_info['shader_prim_path']))
                if not shader:
                    carb.log_warn('shader prim not found for applying edits')
                    return

                update_shader_color(feature_info)


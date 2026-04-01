# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb
from pxr import UsdGeom, UsdShade, Gf, Sdf

from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features_api as features_api_module
from omni.earth_2_command_center.app.globe_view.utils import create_unique_prim_path, toggle_visibility
from omni.earth_2_command_center.app.geo_utils import get_geo_converter
from omni.earth_2_command_center.app.shading import get_shader_library, create_material_prim

from ..features.airport_marker_feature import AirportMarkerFeature


class AirportMarkerDelegate:
    """Delegate that renders AirportMarkerFeature as spheres on the globe."""

    def __init__(self, viewport):
        self._viewport = viewport
        self._representations = {}

    def __call__(self, event, globe_view):
        change = event.payload["change"]
        usd_stage = globe_view.usd_stage
        feature_id = event.sender

        # Clear all
        if change["id"] == features_api_module.FeatureChange.FEATURE_CLEAR["id"]:
            for fid, rep in self._representations.items():
                usd_stage.RemovePrim(rep["prim_path"])
            self._representations.clear()
            return

        # Remove
        if change["id"] == features_api_module.FeatureChange.FEATURE_REMOVE["id"]:
            if feature_id in self._representations:
                usd_stage.RemovePrim(self._representations[feature_id]["prim_path"])
                del self._representations[feature_id]
            return

        feature = get_state().get_features_api().get_feature_by_id(feature_id)
        if not isinstance(feature, AirportMarkerFeature):
            return

        # Add
        if feature_id not in self._representations:
            self._create_marker(feature_id, feature, usd_stage)

        # Property change
        elif change["id"] == features_api_module.FeatureChange.PROPERTY_CHANGE["id"]:
            prop = event.payload.get("property")
            rep = self._representations[feature_id]

            if prop == "active":
                toggle_visibility(usd_stage, rep["prim_path"], event.payload["new_value"])
            elif prop in ("latitude", "longitude", "altitude"):
                self._update_position(feature, usd_stage, rep["prim_path"])
            elif prop in ("color", "flight_category"):
                self._update_color(feature, usd_stage, rep["shader_path"])

    def _create_marker(self, feature_id, feature: AirportMarkerFeature, usd_stage):
        path = create_unique_prim_path(prefix="airport_marker")
        sphere = UsdGeom.Sphere.Define(usd_stage, path)
        sphere.GetRadiusAttr().Set(feature.radius)

        # Material
        mtl_path = Sdf.Path(str(path) + "/Material")
        shader_spec = get_shader_library().get_shader_spec("BasicMaterial")
        material_prim, shader_prim = create_material_prim(usd_stage, mtl_path, shader_spec)

        shader = UsdShade.Shader(shader_prim)
        shader.GetInput("emission_intensity").Set(10000)
        shader.GetInput("emission_color").Set(feature.color)

        # Bind material
        sphere.GetPrim().ApplyAPI(UsdShade.MaterialBindingAPI)
        UsdShade.MaterialBindingAPI(sphere.GetPrim()).Bind(material_prim)

        # Position
        geo_converter = get_geo_converter()
        x, y, z = geo_converter.lonlatalt_to_xyz(
            feature.longitude, feature.latitude, feature.altitude
        )
        UsdGeom.XformCommonAPI(sphere.GetPrim()).SetTranslate(Gf.Vec3d(x, y, z))

        self._representations[feature_id] = {
            "prim_path": path,
            "material_path": material_prim.GetPath(),
            "shader_path": shader_prim.GetPath(),
        }

    def _update_position(self, feature: AirportMarkerFeature, usd_stage, prim_path):
        geo_converter = get_geo_converter()
        x, y, z = geo_converter.lonlatalt_to_xyz(
            feature.longitude, feature.latitude, feature.altitude
        )
        prim = usd_stage.GetPrimAtPath(prim_path)
        if prim:
            UsdGeom.XformCommonAPI(prim).SetTranslate(Gf.Vec3d(x, y, z))

    def _update_color(self, feature: AirportMarkerFeature, usd_stage, shader_path):
        prim = usd_stage.GetPrimAtPath(shader_path)
        if prim:
            shader = UsdShade.Shader(prim)
            shader.GetInput("emission_color").Set(feature.color)

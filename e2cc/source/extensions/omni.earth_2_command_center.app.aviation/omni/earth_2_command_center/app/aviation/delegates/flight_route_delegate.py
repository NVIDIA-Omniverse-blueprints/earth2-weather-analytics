# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import numpy as np
import carb
from pxr import UsdGeom, UsdShade, Sdf

from omni.earth_2_command_center.app.core import get_state
import omni.earth_2_command_center.app.core.features_api as features_api_module
from omni.earth_2_command_center.app.globe_view.utils import create_unique_prim_path, toggle_visibility
from omni.earth_2_command_center.app.geo_utils import get_geo_converter
from omni.earth_2_command_center.app.shading import get_shader_library, create_material_prim

from ..features.flight_route_feature import FlightRouteFeature


class FlightRouteDelegate:
    """Delegate that renders FlightRouteFeature as BasisCurves on the globe."""

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

        # Add or update
        feature = get_state().get_features_api().get_feature_by_id(feature_id)
        if not isinstance(feature, FlightRouteFeature):
            return

        if feature_id not in self._representations:
            self._create_route(feature_id, feature, usd_stage)
        elif change["id"] == features_api_module.FeatureChange.PROPERTY_CHANGE["id"]:
            prop = event.payload.get("property")
            if prop == "active":
                toggle_visibility(
                    usd_stage,
                    self._representations[feature_id]["prim_path"],
                    event.payload["new_value"],
                )
            elif prop in ("points", "waypoints", "hazard_scores"):
                # Recreate geometry
                usd_stage.RemovePrim(self._representations[feature_id]["prim_path"])
                self._create_route(feature_id, feature, usd_stage)

    def _create_route(self, feature_id, feature: FlightRouteFeature, usd_stage):
        if feature.points is None or len(feature.points) < 2:
            return

        path = create_unique_prim_path(prefix="flight_route")
        prim = UsdGeom.BasisCurves.Define(usd_stage, path)
        prim.GetTypeAttr().Set(UsdGeom.Tokens.linear)
        prim.GetWrapAttr().Set(UsdGeom.Tokens.nonperiodic)

        # Project lat/lon/alt to xyz
        geo_converter = get_geo_converter()
        pts = feature.points
        x, y, z = geo_converter.lonlatalt_to_xyz(
            pts[:, 1], pts[:, 0], pts[:, 2]
        )
        proj_points = np.column_stack([x, y, z])
        prim.GetPointsAttr().Set(proj_points)
        prim.GetCurveVertexCountsAttr().Set([len(proj_points)])

        # Width
        prim.SetWidthsInterpolation(UsdGeom.Tokens.constant)
        prim.GetWidthsAttr().Set([feature.width])

        # Material
        mtl_path = Sdf.Path(str(path) + "/Material")
        shader_spec = get_shader_library().get_shader_spec("BasicMaterial")
        material_prim, shader_prim = create_material_prim(usd_stage, mtl_path, shader_spec)

        shader = UsdShade.Shader(shader_prim)
        shader.GetInput("emission_intensity").Set(10000)

        # Color based on average hazard score
        if feature.hazard_scores and len(feature.hazard_scores) > 0:
            avg_hazard = sum(feature.hazard_scores) / len(feature.hazard_scores)
            color = FlightRouteFeature.hazard_to_color(avg_hazard)
        else:
            color = feature.color
        shader.GetInput("emission_color").Set(color)

        # Bind material
        bind_prim = usd_stage.GetPrimAtPath(path)
        if bind_prim and not bind_prim.HasAPI(UsdShade.MaterialBindingAPI):
            bind_prim.ApplyAPI(UsdShade.MaterialBindingAPI)
        if bind_prim:
            UsdShade.MaterialBindingAPI(bind_prim).Bind(material_prim)

        self._representations[feature_id] = {
            "prim_path": path,
            "shader_path": shader_prim.GetPath(),
        }

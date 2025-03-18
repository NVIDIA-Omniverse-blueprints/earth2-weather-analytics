# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from typing import Any, Callable, cast

import carb
import carb.events
import omni.usd
from carb.settings import get_settings
from omni.earth_2_command_center.app.core.features_api import Feature, FeatureChange, FeaturesAPI, Sun
from pxr import Usd

from ..features import ProjectedVolumeFeature
from .volume_manager import ProjectedVolumeManager


class VolumeFeatureManager:
    _features_api: FeaturesAPI
    _feature_event_sub: carb.events.ISubscription | None
    _volume_manager: ProjectedVolumeManager
    _active_features_count: int

    def __init__(self, features_api: FeaturesAPI):
        self._features_api = features_api
        self._volume_manager = ProjectedVolumeManager()
        event_stream = features_api.get_event_stream()
        self._feature_event_sub = event_stream.create_subscription_to_push(self._on_feature_event)
        self._active_features_count = 0

    def __del__(self):
        self.dispose()

    def dispose(self):
        self._feature_event_sub = None

        # remove all index features.
        for feature in self._features_api.get_by_type(ProjectedVolumeFeature):
            self._remove(feature.id)
            self._features_api.remove_feature(feature)

        self._volume_manager.dispose()

    @staticmethod
    def _is_volume_feature(feature_type: str):
        return feature_type in (ProjectedVolumeFeature.feature_type,)

    def _on_feature_event(self, event: carb.events.IEvent):
        change: FeatureChange = event.payload["change"]
        change_id: int = change["id"]
        feature_type: str = event.payload["feature_type"]
        if change_id == FeatureChange.FEATURE_CLEAR["id"]:
            pass
        elif change_id == FeatureChange.FEATURE_REMOVE["id"] and VolumeFeatureManager._is_volume_feature(feature_type):
            f_id = event.payload["id"]
            self._remove(f_id)
        elif change_id == FeatureChange.FEATURE_ADD["id"] and VolumeFeatureManager._is_volume_feature(feature_type):
            f_id = event.payload["id"]
            if f := self._features_api.get_feature_by_id(f_id):
                self._add(f)
        elif change_id == FeatureChange.PROPERTY_CHANGE["id"]:
            if VolumeFeatureManager._is_volume_feature(feature_type):
                f_id = event.payload["id"]
                if f := self._features_api.get_feature_by_id(f_id):
                    property_name = event.payload["property"]
                    self._handle_property_change(f, property_name, event.payload["new_value"])
            elif feature_type == Sun.feature_type:
                sun_feature_id = event.payload["id"]
                sun_feature = self._features_api.get_feature_by_id(sun_feature_id)
                if sun_feature and sun_feature.active:
                    self._volume_manager.sun_lat = sun_feature.latitude
                    self._volume_manager.sun_lon = sun_feature.longitude
                else:
                    pass  # Should disable sun use for all features

    def _add(self, feature: Feature):
        self._volume_manager.add_feature(cast(ProjectedVolumeFeature, feature))
        self._active_features_count += 1

        get_settings().set_int("/rtx/index/compositeEnabled", 1)

        # FIXME: Get the sun feature to correctly fill the sun latitude and longitude

    def _remove(self, feature_id: int):
        self._volume_manager.remove_feature(feature_id)
        self._active_features_count -= 1
        get_settings().set_int("/rtx/index/compositeEnabled", self._active_features_count != 0)

    def _handle_property_change(self, feature: Feature, property_name: str, property_value: Any):
        if property_name == "active":
            self._volume_manager.set_feature_visibility(cast(ProjectedVolumeFeature, feature), bool(property_value))

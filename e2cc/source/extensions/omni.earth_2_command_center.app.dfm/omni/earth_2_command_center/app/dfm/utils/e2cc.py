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
import json
import os
import uuid
import numpy as np

from datetime import datetime
from typing import Any, List, Optional

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence
from omni.earth_2_command_center.app.core.features.image import Image
from omni.earth_2_command_center.app.core.features_api import FeatureChange
from omni.earth_2_command_center.app.core.utils import (
    latlong_rect_to_affine_mapping,
    affine_mapping_to_shader_param_value,
)

class ImageFeature():
    _image_features: dict[str, "ImageFeature"] = {}
    _cb_subscription = None

    def __init__(self, key: str):
        self._timed_sequence_rgb: TimestampedSequence = None
        self._timed_sequence_alpha: TimestampedSequence = None
        self._image: Image = ImageFeature.create_image(key)
        self._key: str = key

    @staticmethod
    def create_image(key: str) -> Image:
        features_api = get_state().get_features_api()
        image = features_api.create_image_feature()
        features_api.add_feature(image)
        image.name = key
        return image

    @classmethod
    def _on_feature_event(cls, event):
        change = event.payload['change']
        if change['id'] == FeatureChange.FEATURE_CLEAR['id']:
            # All features were cleared - just delete everything
            for feature in cls._image_features.values():
                feature.set_active(False)
            cls._image_features.clear()
        elif change['id'] == FeatureChange.FEATURE_REMOVE['id']:
            # A feature has been removed, we need to figure out which one and remove it
            sender_id = event.sender
            for key in cls._image_features:
                if cls._image_features[key].image.id == sender_id:
                    cls._image_features[key].set_active(False)
                    del cls._image_features[key]
                    break
        # check if active state has changed so we can propagate it to the underlying dynamic texture
        elif change['id'] == FeatureChange.PROPERTY_CHANGE['id'] and event.payload['property'] == 'active':
            sender_id = event.sender
            for feature in cls._image_features.values():
                if feature.image.id == sender_id:
                    feature.set_active(event.payload['new_value'])

    @classmethod
    def _register_cb(cls):
        if not cls._cb_subscription:
            feature_event_stream = get_state().get_features_api().get_event_stream()
            cls._cb_subscription = feature_event_stream.create_subscription_to_pop(cls._on_feature_event)

    @classmethod
    def get_image_feature(cls, key: str) -> "ImageFeature":
        image_feature = cls._image_features.get(key, None)
        if not image_feature:
            cls._register_cb()
            image_feature = ImageFeature(key)
            cls._image_features[key] = image_feature
        return image_feature

    @property
    def image(self) -> Image:
        return self._image

    def set_active(self, active: bool):
        self._image.active = active
        if self._timed_sequence_alpha:
            self._timed_sequence_alpha.tex.active = active
        if self._timed_sequence_rgb:
            self._timed_sequence_rgb.tex.active = active

    def _get_alpha_seq(self):
        if not self._timed_sequence_alpha:
            self._timed_sequence_alpha = TimestampedSequence()
            self._timed_sequence_alpha.target_url = f"dynamic://sequence_{uuid.uuid1()}"
            self._image.alpha_sources = [self._timed_sequence_alpha.target_url]
        return self._timed_sequence_alpha

    def _get_rgb_seq(self):
        if not self._timed_sequence_rgb:
            self._timed_sequence_rgb = TimestampedSequence()
            self._timed_sequence_rgb.target_url = f"dynamic://sequence_{uuid.uuid1()}"
            self._image.sources = [self._timed_sequence_rgb.target_url]
        return self._timed_sequence_rgb

    def update_alpha_images(self, urls: List[str], dates: List[datetime]):
        seq = self._get_alpha_seq()
        assert len(urls) == len(dates)
        seq.insert_multiple(zip(dates, urls))

    def update_rgb_images(self, urls: List[str], dates: List[datetime]):
        seq = self._get_rgb_seq()
        assert len(urls) == len(dates)
        seq.insert_multiple(zip(dates, urls))

    def update_date_range(self, dates: List[datetime]):
        times_sorted = sorted(dates)
        self._image.time_coverage_extend_to_include(times_sorted[0], times_sorted[-1])

    def update_remapping(self, meta_data: dict[str, Any]):
        self._image.remapping = self._image.remapping | meta_data.get("remapping", {})

    def update_transform(self, meta_data: dict[str, Any],
                                is_full_globe: bool = True,
                                adjust_offsets: bool = False):
        lon = None
        lat = None
        if "lon_minmax" in meta_data and "lat_minmax" in meta_data:
            lon = meta_data["lon_minmax"]
            lat = meta_data["lat_minmax"]
        elif "latlon_min" in meta_data and "latlon_max" in meta_data:
            min = meta_data["latlon_min"]
            max = meta_data["latlon_max"]
            lon = (min[1], max[1])
            lat = (min[0], max[0])
        if lat and lon:
            if adjust_offsets:
                self._image.longitudinal_offset = np.deg2rad(lon[0])
                lon[1] = lon[1]-lon[0]
                lon[0] = 0.0
            # no affine transform if we use a full globe texture
            if not is_full_globe:
                self._image.affine = affine_mapping_to_shader_param_value(
                    latlong_rect_to_affine_mapping(
                        lon_min=lon[0],
                        lon_max=lon[1],
                        lat_min=lat[0],
                        lat_max=lat[1],
                        is_in_radians=False,
                    )
                )

    def update_metadata(self, meta_data: dict[str, Any]):
        ## Add meta data to image object
        self._image.meta = meta_data


def create_dfm_image_feature(
    image_urls: List[str],
    alpha_image_urls: List[str],
    image_timestamps: List[datetime],
    feature_name: str,
    meta_data: dict[str, Any] = {},
    cmap: str | None = None,
    is_full_globe: bool = True,
    rescale_timeline: bool = True,
    adjust_offsets: bool = False
) -> ImageFeature:
    """Creates an image feature from a DFM response body and adds it to the stage

    Parameters
    ----------
    image_urls : List[str]
        URLs of RGB images to load
    alpha_image_urls : List[str]
        URLs of alpha images to load
    image_timestamps : List[datetime]
        time stamps of the input images
    feature_name : str
        name of the layer in the E2CC UI, needs to be unique
    meta_data : dict[str, Any], optional
        metadata to attach to the image
    cmap : str, optional
        colormap to use for the grayscale image
    is_full_globe : bool, optional
        set if input textures are spanning the entire globe (disables affine transform)
    rescale_timeline : bool, optional
        rescale the timeline to the feature
    adjust_offsets: bool, optional
        adjusts the longitudinal bounds to be in the positive range and adjusts the offset accordingly

    Returns
    -------
    ImageFeature
        E2CC image feature
    """
    carb.log_info(f"Creating DFM Image feature {feature_name}")

    # For use of local caching, not nucleus
    dfm_cache_path = os.getenv("DFM_CACHE_PATH", "/cache")
    e2cc_cache_path = os.getenv("E2CC_CACHE_PATH", "/cache")

    image_urls = [f.replace(dfm_cache_path, e2cc_cache_path) for f in image_urls]
    alpha_image_urls = [f.replace(dfm_cache_path, e2cc_cache_path) for f in alpha_image_urls]

    for f in image_urls + alpha_image_urls:
        if not os.path.exists(f):
            raise FileExistsError(
                f"Texture file not found, is your cache location correct? {f}"
            )

    # Create an image feature and add the image path
    image_feature = ImageFeature.get_image_feature(feature_name)

    # Register rgb images with timestamps
    if image_urls:
        image_feature.update_rgb_images(image_urls, image_timestamps)

    # Register alpha images with timestamps
    if alpha_image_urls:
        image_feature.update_alpha_images(alpha_image_urls, image_timestamps)

    # Extend timerange with min max of input timestamps
    image_feature.update_date_range(image_timestamps)

    # Update metadata
    image_feature.update_metadata(meta_data)

    image_feature.update_transform(meta_data, is_full_globe, adjust_offsets)

    image_feature.update_remapping(meta_data)

    # Set colormap
    if cmap:
        image_feature.image.colormap = cmap

    # Activate image
    image_feature.image.active = True

    # Rescale the time bar to the range of the currently created or updated layer
    if rescale_timeline:
        get_state().get_time_manager().include_all_features(features=[image_feature.image])

    carb.log_info("Image complete")
    return image_feature

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'Image' ]

from .feature import *

from typing import Any, List, Callable, Optional, TypeVar

class Image(Feature):
    feature_type = "Image"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self._projection = 'latlong'
        self._sources: list[str] = []
        self._alpha_sources: list[str] = []
        self._colormap: Optional[str] = None
        self._colormap_source_channel: Optional[str] = None
        self._flip_u: bool = False
        self._flip_v: bool = False
        self._longitudinal_offset: Optional[float] = None
        self._remapping: dict[str, float] = {'input_min': 0.0, 'input_max': 1.0, 'output_min': 0.0, 'output_max': 1.0, 'output_gamma': 1.0}
        self._affine: Optional[list[Any]] = None

    @property
    def projection(self):
        return self._projection

    @projection.setter
    def projection(self, proj):
        self._property_change('projection', proj)

    @property
    def sources(self):
        return self._sources.copy()

    @sources.setter
    def sources(self, sources):
        self._property_change('sources', sources)

    @property
    def alpha_sources(self):
        return self._alpha_sources.copy()

    @alpha_sources.setter
    def alpha_sources(self, sources):
        self._property_change('alpha_sources', sources)

    @property
    def colormap(self):
        return self._colormap

    @colormap.setter
    def colormap(self, colormap):
        self._property_change('colormap', colormap)

    @property
    def colormap_source_channel(self):
        return self._colormap_source_channel

    @colormap_source_channel.setter
    def colormap_source_channel(self, colormap_source_channel):
        self._property_change('colormap_source_channel', colormap_source_channel)

    @property
    def flip_u(self):
        return self._flip_u

    @flip_u.setter
    def flip_u(self, flip_u):
        self._property_change('flip_u', flip_u)

    @property
    def flip_v(self):
        return self._flip_v

    @flip_v.setter
    def flip_v(self, flip_v):
        self._property_change('flip_v', flip_v)

    @property
    def longitudinal_offset(self):
        return self._longitudinal_offset

    @longitudinal_offset.setter
    def longitudinal_offset(self, longitudinal_offset):
        self._property_change('longitudinal_offset', longitudinal_offset)

    @property
    def remapping(self):
        # NOTE: we return a copy beacause we can't trigger events on individual key changes
        # we could implement a custom type instead and implement __setitem__.
        return self._remapping.copy()

    @remapping.setter
    def remapping(self, remapping):
        self._property_change('remapping', remapping)

    @property
    def affine(self):
        # NOTE: we return a copy beacause we can't trigger events on individual key changes
        # we could implement a custom type instead and implement __setitem__.
        if self._affine is not None:
            return self._affine.copy()
        else:
            return None

    @affine.setter
    def affine(self, affine):
        self._property_change('affine', affine)

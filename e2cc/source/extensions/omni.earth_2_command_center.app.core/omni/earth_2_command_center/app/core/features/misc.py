# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'Marker', 'Volume', 'Curves' ]

import copy

from .feature import *

from typing import Any, List, Callable, Optional, TypeVar

class Marker(Feature):
    feature_type = "Marker"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class Volume(Feature):
    feature_type = "Volume"

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

class Curves(Feature):
    feature_type = "Curves"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO: explain what attributes can be of what length and how this impacts
        # rendering
        self._projection = None
        self._periodic = False
        self._points = None
        self._points_per_curve = None
        self._color = (1,1,1)
        self._width = 1

    @property
    def projection(self):
        return self._projection

    @projection.setter
    def projection(self, projection):
        self._property_change('projection', projection)

    @property
    def periodic(self):
        return self._periodic

    @periodic.setter
    def periodic(self, periodic):
        self._property_change('periodic', periodic)

    @property
    def points(self):
        return self._points

    @points.setter
    def points(self, points):
        self._property_change('points', points)

    @property
    def points_per_curve(self):
        return copy.copy(self._points_per_curve)

    @points_per_curve.setter
    def points_per_curve(self, points_per_curve):
        self._property_change('points_per_curve', points_per_curve)

    @property
    def color(self):
        return copy.copy(self._color)

    @color.setter
    def color(self, color):
        self._property_change('color', color)

    @property
    def width(self):
        return copy.copy(self._width)

    @width.setter
    def width(self, width):
        self._property_change('width', width)

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from copy import deepcopy
from dataclasses import dataclass, field

from .typing import ColorRGBA, RangeF1D


@dataclass
class Colormap:
    domain: RangeF1D = (0.0, 1.0)
    rgbaPoints: list[ColorRGBA] = field(default_factory=lambda: deepcopy([(1, 1, 1, 0), (1, 1, 1, 1)]))
    xPoints: list[float] = field(default_factory=lambda: deepcopy([0.0, 1.0]))


@dataclass
class AtmosphericScattering(Colormap):
    rgbaPoints: list[ColorRGBA] = field(
        default_factory=lambda: [
            # (0, 0, 0.000001, 0),
            # (0, 0.15548155, 0.5289575, 0.0005),
            # (0.063952565, 0.25188494, 1, 0.0005),
            # (0, 0.31604084, 0.8185328, 0.0025),
            # (0.9076787, 0.9645461, 0.996139, 0.004),
            # (1, 0.99999, 1, 0.005),
            (0.01, 0.05, 0.5, 0.0),
            (0.03, 0.4, 0.6, 0.007),
            (1.0, 1.0, 1.0, 0.01),
        ]
    )
    xPoints: list[float] = field(
        # default_factory=lambda: [0, 0.2215, 0.4516, 0.7613, 0.9484, 1]
        default_factory=lambda: [0.0, 0.99, 1.0]
    )


@dataclass
class WhiteRamp(Colormap):
    pass


@dataclass
class Clouds(Colormap):
    rgbaPoints: list[ColorRGBA] = field(
        default_factory=lambda: [
            (0.0, 0.0, 0.0, 0.0),
            (0.5, 0.5, 0.5, 0.5),
            (1.0, 1.0, 1.0, 1.0),
        ]
    )
    xPoints: list[float] = field(default_factory=lambda: [0, 0.0001, 1])


@dataclass
class GreyRamp(Colormap):
    rgbaPoints: list[ColorRGBA] = field(default_factory=lambda: [(1.0, 1.0, 1.0, 0.0), (1.0, 1.0, 1.0, 1.0)])
    xPoints: list[float] = field(default_factory=lambda: [0.0, 1.0])


@dataclass
class RedRamp(Colormap):
    rgbaPoints: list[ColorRGBA] = field(default_factory=lambda: [(1.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 1.0)])
    xPoints: list[float] = field(default_factory=lambda: [0.0, 1.0])


@dataclass
class GreenRamp(Colormap):
    rgbaPoints: list[ColorRGBA] = field(default_factory=lambda: [(0.0, 1.0, 0.0, 0.0), (0.0, 1.0, 0.0, 1.0)])
    xPoints: list[float] = field(default_factory=lambda: [0.0, 1.0])


@dataclass
class BlueRamp(Colormap):
    rgbaPoints: list[ColorRGBA] = field(default_factory=lambda: [(0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 1.0, 1.0)])
    xPoints: list[float] = field(default_factory=lambda: [0.0, 1.0])

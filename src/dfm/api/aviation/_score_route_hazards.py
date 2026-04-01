# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Score flight route segments for aviation hazards."""

from typing import Dict, Literal, Optional
from .. import FunctionCall, FunctionRef


class ScoreRouteHazards(FunctionCall, frozen=True):
    """
    Score route segments for aviation hazards based on extracted weather data.

    Computes a weighted hazard score per route segment from turbulence,
    icing, and wind shear metrics. Each metric is normalized to 0-1
    before weighting.

    Args:
        data: FunctionRef for route weather Dataset (from ExtractRouteWeather)
        weights: Optional dict of hazard weights. Defaults to
                 {"turbulence": 0.4, "icing": 0.3, "wind_shear": 0.3}
        output_name: Name of the output hazard score variable
    """

    api_class: Literal["dfm.api.aviation.ScoreRouteHazards"] = (
        "dfm.api.aviation.ScoreRouteHazards"
    )
    data: FunctionRef
    weights: Optional[Dict[str, float]] = None
    output_name: str = "hazard_score"

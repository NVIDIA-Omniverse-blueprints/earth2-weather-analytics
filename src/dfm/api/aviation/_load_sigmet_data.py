# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Load SIGMET/AIRMET advisories from Aviation Weather Center."""

from typing import Literal
from .. import FunctionCall


class LoadSigmetData(FunctionCall, frozen=True):
    """
    Load SIGMET or AIRMET advisories from the FAA Aviation Weather Center.

    Returns hazard area polygons with severity, type, and altitude information
    for significant meteorological events (turbulence, icing, convection, etc.).

    Args:
        hazard_type: Type of advisory to fetch ("sigmet" or "airmet")
        return_geojson: If True, include raw GeoJSON data in response
        return_meta_data: If True, include metadata in response
    """

    api_class: Literal["dfm.api.aviation.LoadSigmetData"] = (
        "dfm.api.aviation.LoadSigmetData"
    )
    hazard_type: Literal["sigmet", "airmet"] = "sigmet"
    return_geojson: bool = False
    return_meta_data: bool = False

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Load full METAR observations from Aviation Weather Center."""

from typing import List, Literal, Optional
from .. import FunctionCall


class LoadMetarData(FunctionCall, frozen=True):
    """
    Load current METAR observations from the FAA Aviation Weather Center.

    Returns full METAR decode including visibility, ceiling, temperature,
    dewpoint, wind, altimeter setting, and flight category (VFR/MVFR/IFR/LIFR).

    Args:
        stations: Optional list of ICAO station identifiers to filter
        bbox: Optional bounding box as "minLat,minLon,maxLat,maxLon"
        return_geojson: If True, include raw GeoJSON data in response
        return_meta_data: If True, include metadata in response
    """

    api_class: Literal["dfm.api.aviation.LoadMetarData"] = (
        "dfm.api.aviation.LoadMetarData"
    )
    stations: Optional[List[str]] = None
    bbox: Optional[str] = None
    return_geojson: bool = False
    return_meta_data: bool = False

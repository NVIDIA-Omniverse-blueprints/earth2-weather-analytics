# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Load Terminal Aerodrome Forecasts from Aviation Weather Center."""

from typing import List, Literal, Optional
from .. import FunctionCall


class LoadTafData(FunctionCall, frozen=True):
    """
    Load TAF (Terminal Aerodrome Forecast) data from the FAA Aviation Weather Center.

    Returns structured forecast data for airports including wind, visibility,
    ceiling, and weather phenomena forecasts.

    Args:
        stations: Optional list of ICAO station identifiers
        return_geojson: If True, include raw GeoJSON data in response
        return_meta_data: If True, include metadata in response
    """

    api_class: Literal["dfm.api.aviation.LoadTafData"] = (
        "dfm.api.aviation.LoadTafData"
    )
    stations: Optional[List[str]] = None
    return_geojson: bool = False
    return_meta_data: bool = False

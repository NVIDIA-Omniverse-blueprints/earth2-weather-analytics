# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Load Pilot Reports from Aviation Weather Center."""

from typing import Literal, Optional
from .. import FunctionCall


class LoadPirepData(FunctionCall, frozen=True):
    """
    Load PIREP (Pilot Report) data from the FAA Aviation Weather Center.

    Returns pilot reports of in-flight conditions including turbulence,
    icing, wind, and visibility observations at altitude.

    Args:
        bbox: Optional bounding box as "minLat,minLon,maxLat,maxLon"
        age_hours: Maximum age of reports in hours (default 2)
        return_geojson: If True, include raw GeoJSON data in response
        return_meta_data: If True, include metadata in response
    """

    api_class: Literal["dfm.api.aviation.LoadPirepData"] = (
        "dfm.api.aviation.LoadPirepData"
    )
    bbox: Optional[str] = None
    age_hours: int = 2
    return_geojson: bool = False
    return_meta_data: bool = False

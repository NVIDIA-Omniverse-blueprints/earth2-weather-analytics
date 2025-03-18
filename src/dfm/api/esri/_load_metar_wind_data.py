# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""DfmFunction to load NOAA METAR Current Wind Data"""

from typing import Literal

from .. import FunctionCall


class LoadMetarWindData(FunctionCall, frozen=True):
    """
    Function to load current wind data from NOAA METAR stations and buoys via ESRI's Feature Service.

    Args:
        layer: Layer to load (stations or buoys)

    Function Returns:
        GeoJSON data containing current wind observations (and/or metadata).

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.esri.LoadMetarWindData"] = (
        "dfm.api.esri.LoadMetarWindData"
    )
    # Layer to load (stations or buoys)
    layer: Literal["stations", "buoys"] = "stations"
    # if True, the response will directly contain the geojson data
    return_geojson: bool = False
    # if True, the response will contain the metadata
    return_meta_data: bool = False

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""DfmFunction to load ESRI US Wind Forecast Data"""

from typing import Literal, Optional

from .. import FunctionCall


class LoadUSWindForecastData(FunctionCall, frozen=True):
    """
    Function to load US Wind Forecast data from ESRI's Wind Forecast service.

    Args:
        layer: Layer of the US Wind Forecast data to load

    Function Returns:
        GeoJSON data of the US Wind Forecast data (and/or metadata).

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.esri.LoadUSWindForecastData"] = (
        "dfm.api.esri.LoadUSWindForecastData"
    )
    # Layer to load
    layer: Literal[
        "national", "regional", "state", "county", "district", "block_group", "city"
    ] = "national"
    # Time filter to apply to the data (start_time, end_time)
    time_filter: Optional[list[str, str]] = None
    # if True, the response will directly contain the geojson data
    return_geojson: bool = False
    # if True, the response will contain the metadata
    return_meta_data: bool = False

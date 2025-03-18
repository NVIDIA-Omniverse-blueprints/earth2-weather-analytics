# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import xarray
import numpy as np
import pandas as pd
from dfm.service.execute.adapter.data_loader._channels import GFS_CHANNELS


def generate_ecmwf_era5_data():
    """Generates a small dataset with a shape similar to the ecmwf era5 data"""
    np.random.seed(0)
    _10m_u_component_of_wind = 15 + 8 * np.random.randn(3, 2, 4, 6)
    _10m_v_component_of_wind = 10 * np.random.rand(3, 2, 4, 6)
    longitude = [0, 0.25, 0.5, 0.75]
    latitude = [90, 89.75]
    level = [10, 20, 30, 40, 50, 60]
    time = pd.date_range("2019-09-06", periods=3)

    ds = xarray.Dataset(
        data_vars={
            "10m_u_component_of_wind": (
                ["time", "latitude", "longitude", "level"],
                _10m_u_component_of_wind,
            ),
            "10m_v_component_of_wind": (
                ["time", "latitude", "longitude", "level"],
                _10m_v_component_of_wind,
            ),
        },
        coords=dict(time=time, latitude=latitude, longitude=longitude, level=level),
        attrs=dict(description="Weather related data."),
    )
    return ds


def generate_gfs_data():
    """Generates a small dataset with a shape comparable to what comes from the
    NOAA gfs data source"""

    np.random.seed(0)

    data_vars = {}
    for var, acc in GFS_CHANNELS:
        if not acc:  # variables that don't have a lev dimension
            arr = 100 * np.random.rand(3, 2, 4)
            data_vars[var] = (["time", "lat", "lon"], arr)
        else:  # a variable with a lev dimension. In gfs, the data has 1000 levels.
            # However, for shaping the GFS data into something resembling  ERA5
            # only 13 specific levels are needed. So we only create a matrix
            # with lev dimension of 13
            arr = 100 * np.random.rand(3, 13, 2, 4)
            data_vars[var] = (["time", "lev", "lat", "lon"], arr)

    time = pd.date_range("2022-09-06", periods=3)
    lat = [90, 89.75]
    lon = [0, 0.25, 0.5, 0.75]
    lev = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]

    ds = xarray.Dataset(
        data_vars=data_vars,
        coords=dict(time=time, lev=lev, lat=lat, lon=lon),
        attrs=dict(description="Mock-up data for GFS."),
    )
    return ds

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import numpy as np


def gen_era5_channels():
    """
    Generate the channels for ERA5 data.
    """
    base_channels = [
        "u10m",
        "v10m",
        "u100m",
        "v100m",
        "t2m",
        "r2m",
        "sp",
        "msl",
        "tcwv",
    ]
    prefix = ["u", "v", "z", "t", "r", "q"]
    levels = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
    channels = [f"{p}{lev}" for p in prefix for lev in levels]
    return base_channels + channels


def gen_gfs_channels():
    """
    Generate the channels for GFS data.
    """
    base_channels = [
        "ugrd10m",
        "vgrd10m",
        "ugrd100m",
        "vgrd100m",
        "tmp2m",
        "rh2m",
        "pressfc",
        "prmslmsl",
        "pwatclm",
    ]
    base_channel_pairs = [(c, None) for c in base_channels]
    prefix = ["ugrdprs", "vgrdprs", "hgtprs", "tmpprs", "rhprs", "spfhprs"]
    levels = [50, 100, 200, 250, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
    channel_pairs = [(p, {"lev": lev}) for p in prefix for lev in levels]
    return base_channel_pairs + channel_pairs


def gen_gfs_s3_channels():
    """
    Generate the channels for GFS S3 data.
    """
    base_channels = [
        "UGRD::10 m above ground",
        "VGRD::10 m above ground",
        "UGRD::100 m above ground",
        "VGRD::100 m above ground",
        "TMP::2 m above ground",
        "RH::2 m above ground",
        "PRES::surface",
        "PRMSL::mean sea level",
        "PWAT::entire atmosphere (considered as a single layer)",
    ]
    prefix = ["UGRD", "VGRD", "HGT", "TMP", "RH", "SPFH"]
    levels = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]
    channels = [f"{p}::{lev} mb" for p in prefix for lev in levels]
    return base_channels + channels


ERA5_CHANNEL_LON = np.arange(90, -90.25, -0.25).tolist()
ERA5_CHANNEL_LAT = np.arange(0, 360, 0.25).tolist()
ERA5_CHANNELS = gen_era5_channels()
GFS_CHANNELS = gen_gfs_channels()
GFS_S3_CHANNELS = gen_gfs_s3_channels()
ERA5_TO_GFS_MAP = dict(zip(ERA5_CHANNELS, GFS_CHANNELS))
ERA5_TO_GFS_S3_MAP = dict(zip(ERA5_CHANNELS, GFS_S3_CHANNELS))
# easy to screw up the zips by adding vars to one but not the other
assert len(ERA5_CHANNELS) == len(GFS_CHANNELS)
assert len(ERA5_CHANNELS) == len(ERA5_TO_GFS_MAP)
assert len(ERA5_CHANNELS) == len(ERA5_TO_GFS_S3_MAP)

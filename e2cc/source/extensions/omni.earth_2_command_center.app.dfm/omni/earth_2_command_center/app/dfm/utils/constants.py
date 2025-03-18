# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



# Contour ranges for each variable

VARIABLE_LABELS = {
    "w10m": "Wind Speed",  # Combined wind speed
    "u10m": "Zonal Surface Winds",
    "v10m": "Meridional Surface Winds",
    "t2m": "Surface Temperature",
    "tp": "Total Precipitation",
    "tcwv": "Total Column Water Vapour",
}

VARIABLE_RANGE = {
    "v10m": [-25, 25],  # m/s
    "u10m": [-25, 25],  # m/s
    "w10m": [0, 30],    # m/s
    "t2m": [250, 300],  # Kelvin
    "tp": [0.000001, 0.0025], # m
    "tcwv": [0, 90],
}

VARIABLE_UNIT = {
    "v10m": "m/s",
    "u10m": "m/s",
    "w10m": "m/s",
    "t2m": "K",
    "tp": "cm/hr",
    "tcwv": "kg/m^2",
}

VARIABLE_CMAP = {
    "v10m": "vanimo",
    "u10m": "berlin",
    "w10m": "jet",
    "t2m": "RdYlBu_r",
    "tp": "cubehelix",
    "tcwv": "gist_earth",
}
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import json
import cartopy.feature as cfeature

if __name__ == "__main__":
    countries = cfeature.NaturalEarthFeature(
        category='cultural',
        name='admin_0_countries',
        scale='50m',
        facecolor='none',
        edgecolor='black'
    )

    coastline = cfeature.COASTLINE

    result = {
        "type": "FeatureCollection",
        "features": [],
    }

    for geom in coastline.geometries():
        feature = {
            "type": "Feature",
            "geometry": {
                "type": geom.geom_type,
                "coordinates": list(geom.coords)
            }
        }
        result["features"].append(feature)

    with open('coastline.geojson', 'w') as f:
        json.dump(result, f)

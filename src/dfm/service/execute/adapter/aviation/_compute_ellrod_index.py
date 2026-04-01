# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Adapter to compute Ellrod Turbulence Index for clear-air turbulence detection."""

from typing import Any

import numpy as np
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.aviation import ComputeEllrodIndex as ComputeEllrodIndexParams


def _find_var(data: xarray.Dataset, prefix: str, level: int) -> str:
    """Find a variable matching prefix+level naming patterns."""
    candidates = [f"{prefix}{level}", f"{prefix}_{level}", f"{prefix}prs{level}"]
    for c in candidates:
        if c in data.data_vars:
            return c
    return None


def _earth_radius_m():
    return 6.371e6


class ComputeEllrodIndex(
    UnaryAdapter[Provider, None, ComputeEllrodIndexParams], input_name="data"
):
    """Adapter to compute Ellrod Turbulence Index (TI1).

    TI1 = VWS * DEF where:
    - VWS = vertical wind shear between target level and adjacent level
    - DEF = total deformation = sqrt(DST^2 + DSH^2)
    - DST = stretching deformation = du/dx - dv/dy
    - DSH = shearing deformation = dv/dx + du/dy
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ComputeEllrodIndexParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        level = self.params.pressure_level

        # Find u, v at target level
        u_var = _find_var(data, "u", level)
        v_var = _find_var(data, "v", level)
        if not u_var or not v_var:
            raise DataError(
                f"Cannot find u/v wind at {level} hPa. "
                f"Available: {list(data.data_vars)}"
            )

        u = data[u_var]
        v = data[v_var]

        # Compute horizontal deformation on lat/lon grid
        lat = u.coords["latitude"] if "latitude" in u.coords else u.coords["lat"]
        lon = u.coords["longitude"] if "longitude" in u.coords else u.coords["lon"]

        lat_rad = np.deg2rad(lat)
        dlat = np.deg2rad(float(lat[1] - lat[0])) if len(lat) > 1 else np.deg2rad(0.25)
        dlon = np.deg2rad(float(lon[1] - lon[0])) if len(lon) > 1 else np.deg2rad(0.25)

        R = _earth_radius_m()
        # dx varies with latitude
        cos_lat = np.cos(lat_rad)
        dx = R * cos_lat * dlon  # meters
        dy = R * dlat  # meters (constant)

        lat_dim = lat.dims[0]
        lon_dim = lon.dims[0]

        # Finite differences for deformation
        dudx = u.differentiate(lon_dim) / (R * cos_lat * dlon)
        dvdy = v.differentiate(lat_dim) / dy
        dvdx = v.differentiate(lon_dim) / (R * cos_lat * dlon)
        dudy = u.differentiate(lat_dim) / dy

        # Stretching and shearing deformation
        dst = dudx - dvdy
        dsh = dvdx + dudy
        deformation = np.sqrt(dst**2 + dsh**2)

        # Vertical wind shear - find adjacent level
        adjacent_levels = [200, 250, 400, 500, 700, 850]
        vws_level = None
        for adj in adjacent_levels:
            if adj != level:
                u_adj = _find_var(data, "u", adj)
                v_adj = _find_var(data, "v", adj)
                if u_adj and v_adj:
                    vws_level = adj
                    break

        if vws_level is None:
            # Fall back to deformation only
            ellrod = deformation * 1e4  # scale for readability
        else:
            u_adj_var = _find_var(data, "u", vws_level)
            v_adj_var = _find_var(data, "v", vws_level)
            du_vert = data[u_adj_var] - u
            dv_vert = data[v_adj_var] - v
            dp = abs(float(vws_level - level)) * 100.0  # Pa
            vws = np.sqrt(du_vert**2 + dv_vert**2) / dp
            ellrod = vws * deformation * 1e7  # scale to typical TI range 0-12

        ellrod_clipped = ellrod.clip(min=0)
        ellrod_clipped.name = self.params.output_name

        output_ds = ellrod_clipped.to_dataset()
        output_ds[self.params.output_name].attrs.update(
            {
                "description": f"Ellrod Turbulence Index TI1 at {level} hPa",
                "units": "TI",
                "pressure_level_hpa": level,
                "data_min": float(ellrod_clipped.min().data),
                "data_max": float(ellrod_clipped.max().data),
            }
        )
        return output_ds

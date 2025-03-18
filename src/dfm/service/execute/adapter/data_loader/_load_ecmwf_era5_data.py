# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict, List
import time
import random
from pydantic import JsonValue
import xarray

from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter.data_loader._utils import should_filter_variables
from dfm.service.execute.discovery._advised_values import AdvisedValue
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.data_loader import LoadEra5ModelData as LoadEra5ModelDataParams
from dfm.config.adapter.data_loader import LoadEcmwfEra5Data as LoadEcmwfEra5DataConfig
from dfm.service.execute.discovery import (
    field_advisor,
    AdvisedOneOf,
    AdvisedLiteral,
    AdvisedDict,
    AdvisedSubsetOf,
)

from ._xarray_loader_caching_iterator import XarrayLoaderCachingIterator

ALL_VARIABLES = [
    "10m_u_component_of_wind",
    "10m_v_component_of_wind",
    "2m_temperature",
    "angle_of_sub_gridscale_orography",
    "anisotropy_of_sub_gridscale_orography",
    "geopotential",
    "geopotential_at_surface",
    "high_vegetation_cover",
    "lake_cover",
    "lake_depth",
    "land_sea_mask",
    "latitude",
    "level",
    "longitude",
    "low_vegetation_cover",
    "mean_sea_level_pressure",
    "sea_ice_cover",
    "sea_surface_temperature",
    "slope_of_sub_gridscale_orography",
    "soil_type",
    "specific_humidity",
    "standard_deviation_of_filtered_subgrid_orography",
    "standard_deviation_of_orography",
    "surface_pressure",
    "temperature",
    "time",
    "toa_incident_solar_radiation",
    "total_cloud_cover",
    "total_column_water_vapour",
    "total_precipitation",
    "type_of_high_vegetation",
    "type_of_low_vegetation",
    "u_component_of_wind",
    "v_component_of_wind",
    "vertical_velocity",
]


class LoadEcmwfEra5Data(
    NullaryAdapter[Provider, LoadEcmwfEra5DataConfig, LoadEra5ModelDataParams]
):
    """
    A LoadEcmwfEra5Data adapter is an adapter that loads ERA5 data from the ECMWF.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadEcmwfEra5DataConfig,
        params: LoadEra5ModelDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        return self._collect_local_hash_dict_helper(
            url=self.config.url, frequency=self.config.frequency
        )

    def _instantiate_caching_iterator(self):
        cache_fsspec_conf = self.provider.cache_fsspec_conf()
        if cache_fsspec_conf:
            return XarrayLoaderCachingIterator(self, cache_fsspec_conf)
        return None

    @field_advisor("variables")
    async def available_variables(self, _value, _context):
        advice_list: List[JsonValue | AdvisedValue] = [
            v
            for v in ALL_VARIABLES
            if v not in ["latitude", "longitude", "level", "time"]
        ]
        return AdvisedOneOf([AdvisedLiteral("*"), AdvisedSubsetOf(advice_list)])

    @field_advisor("selection")
    async def valid_selections(self, _value, _context):
        none_advice = AdvisedLiteral(None)
        dict_advice = AdvisedDict(
            {
                "time": {
                    "first_date": self.config.first_date,
                    "last_date": self.config.last_date,
                    "frequency": self.config.frequency,
                }
            },
            allow_extras=True,
        )
        return AdvisedOneOf(values=[none_advice, dict_advice])

    def body(self) -> Any:
        # randomize the access so we don't hit the servier all at once
        time_delay = random.uniform(0.01, 1.5)
        time.sleep(time_delay)

        ds = xarray.open_dataset(
            self.config.url,
            cache=False,
            decode_times=True,
            engine=self.config.engine,
            **(self.config.engine_kwargs or {}),
        )

        if self.params.selection:
            selection: Dict[Any, Any] = {
                k: (v if isinstance(v, list) else [v])
                for k, v in self.params.selection.items()
            }
            ds = ds.sel(method="nearest", **selection)

        # pick the selected variables (or all, if no explicit list or '*')
        # This works better than "drop_variables", because it keeps the
        # coordinates intact, whereas drop_variables
        # may also drop labels
        if should_filter_variables(self.params.variables):
            ds = ds[self.params.variables]

        # finally, chunk it up
        # NOTE: depending on caching strategy, we may want to do the chunking
        # before the writing to cache, but for now we don't have a distributed
        # cache, so I move it to after
        if isinstance(self.config.chunks, dict):
            ds = ds.chunk(
                {
                    dim: size
                    for dim, size in self.config.chunks.items()
                    if dim in ds.dims
                }
            )
        else:
            ds = ds.chunk(self.config.chunks)

        return ds

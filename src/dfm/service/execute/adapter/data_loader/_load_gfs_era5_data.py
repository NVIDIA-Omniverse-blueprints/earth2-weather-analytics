# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict
import time
import random
import xarray
from datetime import datetime, timedelta
import dateutil.parser
from concurrent.futures import ThreadPoolExecutor

from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter.data_loader._utils import should_filter_variables
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.data_loader import LoadEra5ModelData as LoadEra5ModelDataParams
from dfm.config.adapter.data_loader import LoadGfsEra5Data as LoadGfsEra5DataConfig
from dfm.service.execute.discovery import (
    field_advisor,
    AdvisedOneOf,
    AdvisedLiteral,
    AdvisedDict,
    AdvisedSubsetOf,
)

from ._channels import ERA5_CHANNELS, ERA5_TO_GFS_MAP

from ._xarray_loader_caching_iterator import XarrayLoaderCachingIterator


class LoadGfsEra5Data(
    NullaryAdapter[Provider, LoadGfsEra5DataConfig, LoadEra5ModelDataParams]
):
    """
    A LoadGfsEra5Data adapter is an adapter that loads GFS ERA5 data.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadGfsEra5DataConfig,
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
        return AdvisedOneOf([AdvisedLiteral("*"), AdvisedSubsetOf(ERA5_CHANNELS)])  # type: ignore

    @field_advisor("selection")
    async def valid_selections(self, _value, _context):
        today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
        advice_d = {
            "time": {
                "first_date": (
                    today - timedelta(days=self.config.offset_first)
                ).strftime("%Y-%m-%d"),
                "last_date": (today - timedelta(days=self.config.offset_last)).strftime(
                    "%Y-%m-%d"
                ),
                "frequency": self.config.frequency,
            }
        }
        none_advice = AdvisedLiteral(None)
        dict_advice = AdvisedDict(advice_d, allow_extras=True)  # type: ignore
        return AdvisedOneOf(values=[none_advice, dict_advice])

    def body(self) -> Any:
        if not self.params.selection or "time" not in self.params.selection:
            raise ValueError(
                "The GfsEra5Data adapter requires a specific time selection. \
                             Please supply something like {'time': '2024-01-31', ...}"
            )

        # randomize the access so we don't hit the servier all at once
        time_delay = random.uniform(0.01, 1.5)
        time.sleep(time_delay)

        # extract year-month-day from the stream_selector and construct the URL
        datestr = dateutil.parser.parse(self.params.selection["time"]).strftime(
            "%Y%m%d"
        )

        # open the dataset
        url = self.config.url.format(datestr)
        self._logger.info("Opening GFS dataset with url %s", url)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(
                xarray.open_dataset,
                url,
                cache=False,
                **(self.config.engine_kwargs or {})
            )
            gfs_ds = future.result(timeout=self.config.timeout)

        # helper to extract the individual data arrays corresponding
        # to the requested era5 variable names
        def extract_da(ds: xarray.Dataset, era5_var: str) -> xarray.DataArray:
            # use the above map to extract the gfs data array
            # corresponding to a given era5 variable name
            gfs_var, sel = ERA5_TO_GFS_MAP[era5_var]
            da = ds[gfs_var]
            if sel:
                da = da.sel(sel)
                # drop the 'lev' coordinate
                da = da.drop_vars(list(sel.keys()))
            da.name = era5_var
            return da

        # apply the helper. Afterwards, the dataset looks like an era5 dataset
        data_arrays = [extract_da(gfs_ds, era5_var) for era5_var in ERA5_CHANNELS]

        # we are dropping the lev coords above, so override technically not needed.
        # But without compat='override' it suddenly takes longer, so keeping it
        era5_ds = xarray.merge(data_arrays, compat="override")

        # apply the selector
        if self.params.selection:
            selection: Dict[Any, Any] = {
                k: (v if isinstance(v, list) else [v])
                for k, v in self.params.selection.items()
            }
            era5_ds = era5_ds.sel(method="nearest", **selection)

        # pick the selected variables (or all, if no explicit list or a '*')
        if should_filter_variables(self.params.variables):
            era5_ds = era5_ds[self.params.variables]

        # finally, chunk it up
        # NOTE: depending on caching strategy, we may want to do the chunking
        # before the writing to cache, but for now we don't have a distributed
        # cache, so I move it to after
        if isinstance(self.config.chunks, dict):
            era5_ds = era5_ds.chunk(
                {
                    dim: size
                    for dim, size in self.config.chunks.items()
                    if dim in era5_ds.dims
                }
            )
        else:
            era5_ds = era5_ds.chunk(self.config.chunks)

        self._logger.info("%s loaded dataset %s", self, era5_ds)
        return era5_ds

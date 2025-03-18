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
import dateutil.parser
from tempfile import mkdtemp

from dfm.service.common.request import DfmRequest
from dfm.service.execute.adapter.data_loader._utils import should_filter_variables
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.data_loader import LoadEra5ModelData as LoadEra5ModelDataParams
from dfm.config.adapter.data_loader import LoadGfsEra5S3Data as LoadGfsEra5S3DataConfig
from dfm.service.execute.discovery import (
    field_advisor,
    AdvisedOneOf,
    AdvisedLiteral,
    AdvisedDict,
    AdvisedSubsetOf,
)

from ._channels import ERA5_CHANNELS
from . import _gfs_utils

from ._xarray_loader_caching_iterator import XarrayLoaderCachingIterator


class LoadGfsEra5S3Data(
    NullaryAdapter[Provider, LoadGfsEra5S3DataConfig, LoadEra5ModelDataParams]
):
    """
    A LoadGfsEra5S3Data adapter is an adapter that loads GFS ERA5 data from S3.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadGfsEra5S3DataConfig,
        params: LoadEra5ModelDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        return self._collect_local_hash_dict_helper(
            bucket_name=self.config.bucket_name, frequency=self.config.frequency
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
        async def async_body():
            if not self.params.selection or "time" not in self.params.selection:
                raise ValueError(
                    "The GfsEra5S3Data adapter requires a specific time selection. \
                                Please supply something like {'time': '2024-01-31', ...}"
                )
            if isinstance(self.params.selection["time"], list):
                raise ValueError(
                    "The GfsEra5S3Data adapter requires a single time selection. \
                                Please supply something like {'time': '2024-01-31', ...}, not a\
                                list. Selection was {self.params.selection}"
                )

            # randomize the access so we don't hit the servier all at once
            time_delay = random.uniform(0.01, 1.5)
            time.sleep(time_delay)

            path = self.config.tmp_download_folder
            if not path:
                path = mkdtemp(suffix="gfs_cache")

            # extract year-month-day from the stream_selector and construct the URL
            date = dateutil.parser.parse(self.params.selection["time"])

            da = await _gfs_utils.GFS(
                bucket_name=self.config.bucket_name,
                cache_folder=path,
                concurrency=self.config.concurrency,
                num_processes=self.config.num_processes,
                keep_cache=False,
                verbose=False,
                read_timeout=self.config.read_timeout,
                connect_timeout=self.config.connect_timeout,
            )(date, self.params.variables)

            # select the data now, because we'll need to pull it to load the
            # real era5 data to change the fields
            if should_filter_variables(self.params.variables):
                da = da.sel({"channel": self.params.variables})

            # Now reshape the array. The GFS data has a fields array with channels as one
            # dimension. We want those channels to be variables.
            data_vars = {}
            for i, channel in enumerate(da["channel"]):
                if len(da.shape) == 4:
                    data_vars[channel.item()] = (
                        ["time", "lat", "lon"],
                        da[:, i, :, :].data,
                    )
                else:
                    data_vars[channel.item()] = (["lat", "lon"], da[i, :, :].data)

            ds = xarray.Dataset(
                data_vars=data_vars,
                coords=dict(
                    time=da["time"],
                    coords=da["channel"],
                    lat=da["lat"],
                    lon=da["lon"],
                ),
                attrs=dict(description="Weather related data."),
            )

            if self.params.selection:
                selection: Dict[Any, Any] = {
                    k: (v if isinstance(v, list) else [v])
                    for k, v in self.params.selection.items()
                }
                ds = ds.sel(method="nearest", **selection)

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

            self._logger.info("%s loaded dataset %s", self, ds)

            return ds

        return async_body()

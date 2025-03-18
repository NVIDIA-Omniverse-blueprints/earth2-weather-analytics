# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""
Invoke a Numerical Weather Prediction (nwp) NIM.
"""

import numpy as np
import pandas as pd
import aiohttp
import xarray
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, AsyncIterator
from tempfile import TemporaryFile

from ._tar_helper import read_file_from_tar, read_tar_header
from dfm.service.common.request import DfmRequest
from dfm.service.common.xarray_schema import XarraySchema, Var, Dim
from dfm.service.execute.adapter.data_loader import XarrayLoaderCachingIterator
from dfm.service.execute.adapter.data_loader._utils import should_filter_variables
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter
from dfm.api.nwp import InvokeNimNwpDnn as InvokeNimNwpDnnParams
from dfm.config.adapter.nwp import InvokeNimFourCastNet as InvokeNimFourCastNetConfig

from dfm.service.execute.discovery import (
    field_advisor,
    AdvisedOneOf,
    AdvisedLiteral,
    AdvisedSubsetOf,
)

FCN_OUTPUT_VARIABLES = [
    "u10m",
    "v10m",
    "u100m",
    "v100m",
    "t2m",
    "sp",
    "msl",
    "tcwv",
    "u50",
    "u100",
    "u150",
    "u200",
    "u250",
    "u300",
    "u400",
    "u500",
    "u600",
    "u700",
    "u850",
    "u925",
    "u1000",
    "v50",
    "v100",
    "v150",
    "v200",
    "v250",
    "v300",
    "v400",
    "v500",
    "v600",
    "v700",
    "v850",
    "v925",
    "v1000",
    "z50",
    "z100",
    "z150",
    "z200",
    "z250",
    "z300",
    "z400",
    "z500",
    "z600",
    "z700",
    "z850",
    "z925",
    "z1000",
    "t50",
    "t100",
    "t150",
    "t200",
    "t250",
    "t300",
    "t400",
    "t500",
    "t600",
    "t700",
    "t850",
    "t925",
    "t1000",
    "q50",
    "q100",
    "q150",
    "q200",
    "q250",
    "q300",
    "q400",
    "q500",
    "q600",
    "q700",
    "q850",
    "q925",
    "q1000",
]


class NimFourCastNetInputSchema(XarraySchema):
    """
    Schema for the input to the FourCastNet NIM.

    Attributes:
        lat: Latitude dimension with 721 points
        lon: Longitude dimension with 1440 points
        time: Single timestamp dimension
    """

    lat: Dim(dtype=np.floating, size=(721, None))  # type: ignore
    lon: Dim(dtype=np.floating, size=(1440, None))  # type: ignore
    # we only allow a single timestamp in the input
    time: Dim(dtype=np.dtype("<M8[ns]"), size=1)  # type: ignore


for output_var in FCN_OUTPUT_VARIABLES:
    NimFourCastNetInputSchema.add_dynamic_attribute(
        output_var, Var(np.floating, "time", "lat", "lon")
    )


class InvokeNimFourCastNet(
    Adapter[Provider, InvokeNimFourCastNetConfig, InvokeNimNwpDnnParams]
):
    """
    Adapter to invoke the FourCastNet NIM.

    Initializes the adapter with the necessary request, provider, configuration,
    parameters and input data adapter. The adapter handles invoking the FourCastNet
    neural weather prediction model through a NIM service.

    Args:
        dfm_request: The DFM request object
        provider: The provider instance
        config: Configuration for the FourCastNet adapter
        params: Parameters for invoking the NIM
        data: Input data adapter
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: InvokeNimFourCastNetConfig,
        params: InvokeNimNwpDnnParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params)
        self._set_input_adapter("data", data)

    def _instantiate_caching_iterator(self):
        cache_fsspec_conf = self.provider.cache_fsspec_conf()
        if cache_fsspec_conf:
            return XarrayLoaderCachingIterator(
                self, cache_fsspec_conf, file_prefix="nim_output"
            )
        return None

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        return self._collect_local_hash_dict_helper(
            exclude_params=[], quality=self.config.seed
        )

    @field_advisor("variables")
    async def available_variables(self, _value, _context):
        return AdvisedOneOf([AdvisedLiteral("*"), AdvisedSubsetOf(FCN_OUTPUT_VARIABLES)])  # type: ignore

    """ entry function """

    async def stream_body(self) -> AsyncIterator[Any]:
        input_adapter = self.get_input_adapter("data")
        input_stream = await input_adapter.get_or_create_stream()
        async for item in input_stream:
            # Check if input is still healthy
            input_stream.raise_if_exception()
            async for i in self.run_nim(item):
                yield i

    async def run_nim(self, data) -> AsyncIterator[Any]:
        # validate input xarray and remove unneeded vars
        NimFourCastNetInputSchema.validate(data, allow_extras=True)
        reduced_data = NimFourCastNetInputSchema.remove_extras(data)

        # stack arrays into a single ndarray
        flattened: np.ndarray = (
            NimFourCastNetInputSchema.translate_vars_to_stacked_ndarray(reduced_data)
        )
        # the stack has channels as the first dim, we want it in second position
        flattened = np.moveaxis(flattened, 0, 1)
        # add one dimension for the batches (always 1, but required by the NIM)
        flattened = np.expand_dims(flattened, axis=0)

        # check that shape of the array ended up as expected
        num_vars = len(NimFourCastNetInputSchema.vars())
        num_lat = NimFourCastNetInputSchema.dims()["lat"].size[0]
        num_lon = NimFourCastNetInputSchema.dims()["lon"].size[0]
        assert flattened.shape == (1, 1, num_vars, num_lat, num_lon)

        # convert the time stamp into iso format with time zone
        dt64 = reduced_data["time"].item()
        # Convert to pandas Timestamp (which handles np.datetime64 natively)
        pd_timestamp = pd.Timestamp(dt64)
        # Localize to UTC
        utc_timestamp = pd_timestamp.tz_localize("UTC")
        # Convert to ISO format string with timezone
        input_time = utc_timestamp.isoformat(timespec="seconds")

        # get the list of output variables
        output_vars = (
            self.params.variables
            if should_filter_variables(self.params.variables)
            else FCN_OUTPUT_VARIABLES
        )

        # create schema to validate the output (dimensions: lat, lon, time; vars: according to params.variables)
        class NimFourCastNetOutputSchema(XarraySchema):
            lat: Dim(dtype=np.floating, size=(721, None))  # type: ignore
            lon: Dim(dtype=np.floating, size=(1440, None))  # type: ignore
            time: Dim(dtype=np.dtype("<M8[ns]"), size=1)  # type: ignore

        for output_var in output_vars:
            NimFourCastNetOutputSchema.add_dynamic_attribute(
                output_var, Var(np.floating, "time", "lat", "lon")
            )

        # need numpy file in byte stream, not the ndarray!
        with TemporaryFile() as temp_np_file:
            np.save(temp_np_file, flattened.astype(np.float32))
            temp_np_file.seek(0)

            # setup parameters that are passed to the NIM via HTTP POST call
            data = aiohttp.FormData()
            data.add_field("input_array", temp_np_file, filename="input_array")
            data.add_field("input_time", str(input_time))
            data.add_field("simulation_length", str(self.params.samples))
            data.add_field("seed", str(self.config.seed))
            if should_filter_variables(self.params.variables):
                data.add_field("variables", ",".join(self.params.variables))

            headers = {
                "accept": "application/x-tar",
            }

            self._logger.info("Sending inference request to NIM")
            timeout = aiohttp.ClientTimeout(total=self.config.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    self.config.url, headers=headers, data=data
                ) as response:
                    response.raise_for_status()
                    while header := await read_tar_header(response.content):
                        with await read_file_from_tar(
                            response.content, header
                        ) as np_file_buffer:
                            data = np.load(np_file_buffer)
                            # Array names are on the form <LEAD_TIME>_<BATCH_IDX>.npy
                            arr_lead_time, _arr_batch_idx = (
                                int(x)
                                for x in Path(header.name).stem.split("_", maxsplit=1)
                            )
                            out_time = utc_timestamp + timedelta(hours=arr_lead_time)

                            # remove batch dimension again from data
                            data = data.squeeze(axis=0)

                            # and now put all results into one xarray:
                            # setup coords and attributes
                            coords = dict(
                                time=pd.to_datetime([out_time]).to_numpy(
                                    dtype=np.dtype("<M8[ns]")
                                ),
                                variable=output_vars,
                                lat=reduced_data["lat"],
                                lon=reduced_data["lon"],
                            )
                            attrs = dict(
                                description=f"Result from FourCastNet NIM at {self.config.url}"
                            )

                            # initially create a DataArray from the numpy array in which all vars are merged into one dimension "variable"
                            da = xarray.DataArray(
                                data,
                                coords=coords,
                                attrs=attrs,
                                dims=["time", "variable", "lat", "lon"],
                            )

                            # and then split the dimension into its vars
                            ds_out = da.to_dataset(dim="variable")

                            # and validate the output before returning it
                            NimFourCastNetOutputSchema.validate(ds_out)

                            if self.params.selection:
                                selection: Dict[Any, Any] = {
                                    k: (v if isinstance(v, list) else [v])
                                    for k, v in self.params.selection.items()
                                }
                                ds_out = ds_out.sel(method="nearest", **selection)

                            yield ds_out

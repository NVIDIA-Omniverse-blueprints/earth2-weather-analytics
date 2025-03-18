# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any
import xarray
import numpy as np
from dfm.service.common.request import DfmRequest
from dfm.service.common.xarray_schema._attr import Attr
from dfm.service.common.xarray_schema._var import Var
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.xarray import ConvertToUint8 as ConvertToUint8Params
from dfm.service.common.xarray_schema import XarraySchema, Dim


class ConvertToUint8(
    UnaryAdapter[Provider, None, ConvertToUint8Params], input_name="data"
):
    """
    A ConvertToUint8 adapter is an adapter that converts a dataset to uint8.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: ConvertToUint8Params,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:

        # check that the input xarray contains the expected dimensions specified in the parameters
        class TextureInputSchema(XarraySchema):
            pass

        TextureInputSchema.add_dynamic_attribute(
            self.params.xydims[0], Dim(np.floating, (0, None))
        )
        TextureInputSchema.add_dynamic_attribute(
            self.params.xydims[1], Dim(np.floating, (0, None))
        )
        TextureInputSchema.add_dynamic_attribute(
            self.params.time_dimension, Dim(np.dtype("datetime64"), (0, None))
        )

        TextureInputSchema.validate(data, allow_extras=True)

        # sum all dimensions except for the xydims requested
        sum_over_dims = [
            dim
            for dim in data.dims
            if dim
            not in (
                self.params.time_dimension,
                self.params.xydims[0],
                self.params.xydims[1],
            )
        ]
        if len(sum_over_dims) > 0:
            data = data.sum(sum_over_dims)

        assert len(data.dims) <= 3

        # transpose to the requested x and y format, if not already
        data = data.transpose(
            self.params.time_dimension,
            self.params.xydims[0],
            self.params.xydims[1],
            missing_dims="ignore",
        )

        # now, normalize the dataset
        as_arr = data.to_array().as_numpy()
        the_min = self.params.min if self.params.min is not None else as_arr.min()
        # first min is in parallel second min across variables
        # else input.min().to_array().min().item()
        the_max = self.params.max if self.params.max is not None else as_arr.max()
        # else input.max().to_array().max().item(0)
        data = ((data - the_min) / (the_max - the_min)).clip(min=0, max=1)

        data_uint8 = (data * 255.0).astype(np.uint8)
        data_uint8.attrs["data_min"] = as_arr.min().data
        data_uint8.attrs["data_max"] = as_arr.max().data

        # The returned xarray dataset may have multiple data variables, but each
        # data variable has the expected 3D shape [time, xdim, ydim]
        class TextureOutputSchema(XarraySchema):
            data_min: Attr
            data_max: Attr

        TextureOutputSchema.add_dynamic_attribute(
            self.params.xydims[0], Dim(np.floating, (0, None))
        )
        TextureOutputSchema.add_dynamic_attribute(
            self.params.xydims[1], Dim(np.floating, (0, None))
        )
        TextureOutputSchema.add_dynamic_attribute(
            self.params.time_dimension, Dim(np.dtype("datetime64"), (0, None))
        )
        for var in data_uint8.data_vars:
            TextureOutputSchema.add_dynamic_attribute(
                var,
                Var(
                    np.dtype("uint8"),
                    self.params.time_dimension,
                    self.params.xydims[0],
                    self.params.xydims[1],
                    minmax=(0, 255),
                ),
            )
        TextureOutputSchema.validate(data_uint8)

        return data_uint8

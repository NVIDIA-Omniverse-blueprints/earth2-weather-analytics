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
import numpy as np
import xarray
from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.common.xarray_schema import XarraySchema, Var, Dim
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.api.xarray import VariableNorm as VariableNormParams


class VariableNorm(UnaryAdapter[Provider, None, VariableNormParams], input_name="data"):
    """
    Adapter to compute the p-norm across multiple variables in an xarray Dataset.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: None,
        params: VariableNormParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def body(self, data: xarray.Dataset) -> Any:
        """Compute the p-norm across multiple variables in an xarray Dataset.

        Parameters
        ----------
        data : xarray.Dataset
            The input dataset containing the variables to compute the norm of.

        Returns
        -------
        xarray.Dataset
            The output dataset containing the computed norm.

        Raises
        ------
        DataError
            If any of the variables in the input dataset are not found.
        """
        # Validate input variables exist
        missing_vars = [
            var for var in self.params.variables if var not in data.data_vars
        ]
        if missing_vars:
            raise DataError(f"Variables {missing_vars} not found in dataset")

        # Create schema for validation
        class NormInputSchema(XarraySchema):
            pass

        # Add dimensions to schema
        for dim in data.dims:
            if dim in data.coords:
                NormInputSchema.add_dynamic_attribute(
                    dim, Dim(data.coords[dim].dtype, (0, None))
                )

        # Add variables to schema
        for var in self.params.variables:
            NormInputSchema.add_dynamic_attribute(
                var, Var(np.floating, *data[var].dims)
            )

        # Create schema for output validation
        class NormOutputSchema(XarraySchema):
            pass

        for dim in data[self.params.variables[0]].dims:
            if dim in data.coords:
                NormOutputSchema.add_dynamic_attribute(
                    dim, Dim(data.coords[dim].dtype, (0, None))
                )
        NormOutputSchema.add_dynamic_attribute(
            self.params.output_name,
            Var(np.floating, *data[self.params.variables[0]].dims),
        )

        # Validate input data
        NormInputSchema.validate(data, allow_extras=True)

        # Stack variables and compute norm
        stacked_vars = xarray.concat(
            [data[var] for var in self.params.variables], dim="variable"
        )
        norm_values = (abs(stacked_vars) ** self.params.p).sum(dim="variable") ** (
            1.0 / self.params.p
        )
        norm_values.name = self.params.output_name
        output_ds = norm_values.to_dataset()

        # Compute min and max values
        # Note that norm_values can be a dask array, which does not support .item(), so we use .data
        # Could check to see if it has proper chunks, to tell if it's a dask array or not
        data_min = norm_values.min().data
        data_max = norm_values.max().data

        # Add some metadata just in case
        output_ds[self.params.output_name].attrs.update(
            {
                "description": f"P-norm (p={self.params.p}) of variables {self.params.variables}",
                "variables_used": self.params.variables,
                "p_value": self.params.p,
                "data_min": data_min,
                "data_max": data_max,
            }
        )

        # Validate output data
        NormOutputSchema.validate(output_ds, allow_extras=False)

        return output_ds

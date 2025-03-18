# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""The main class for the XarraySchema mechanism"""
from typing import Any, Dict, Optional, Union, get_type_hints, get_origin, get_args
import numpy as np
import xarray

from ..exceptions import DataError
from ._attr import Attr
from ._dim import Dim
from ._var import Var
from ._indexed import Indexed


def _is_optional(ftype):
    # (Optional is translated to Union[.., None], and we check if type(None) is i)
    return get_origin(ftype) is Union and type(None) in get_args(ftype)


def _unpack_optional(ftype):
    if get_origin(ftype) is Union and len(get_args(ftype)) > 0:
        ftype = get_args(ftype)[0]
    return ftype


class XarraySchema:
    """The main class for the XarraySchema mechanism"""

    @classmethod
    def validate_fields_present(cls, ds: xarray.Dataset):
        """Verify that all fields defined in the schema are present in the dataset"""
        type_hints = get_type_hints(cls)
        for fname, ftype in type_hints.items():
            if ftype == Attr or isinstance(ftype, Attr):
                if fname not in ds.attrs:
                    raise DataError(
                        f"{cls.__name__} schema attribute {fname} "
                        "is missing in dataset {xarr}"
                    )
            else:
                if fname not in ds and not _is_optional(ftype):
                    if isinstance(ftype, Dim):
                        raise DataError(
                            f"{cls.__name__} schema dimension {fname} "
                            "is missing in dataset {xarr}"
                        )
                    else:
                        raise DataError(
                            f"{cls.__name__} schema variable {fname} "
                            "is missing in dataset {xarr}"
                        )

    @classmethod
    def validate_dims(
        cls, ds: xarray.Dataset, allow_extras: bool = False, check_minmax: bool = False
    ):
        """Validates the Dim fields of the schema"""
        type_hints = get_type_hints(cls)
        # check that actual dims match schema
        for dname, dsize in ds.sizes.items():
            if dname not in type_hints:
                if allow_extras:
                    continue
                else:
                    raise DataError(
                        f"Dataset dimension {dname} "
                        f"is missing in schema {cls.__name__}"
                    )
            dim = _unpack_optional(type_hints[dname])
            if not isinstance(dim, Dim):
                raise DataError(f"{dname} not a Dim in schema")

            if isinstance(dim.size, int):
                if dim.size != dsize:
                    raise DataError(
                        f"Dim {dname} actual size {dsize} "
                        f"doesn't match schema {cls.__name__} size {dim.size}"
                    )
            else:
                # size is a (min, max) tuple
                if dim.size[0] and dsize < dim.size[0]:
                    raise DataError(
                        f"Dim {dname} actual size {dsize} "
                        f"is less than schema {cls.__name__} min size {dim.size}"
                    )
                if dim.size[1] and dsize > dim.size[1]:
                    raise DataError(
                        f"Dim {dname} actual size {dsize} "
                        f"is greater than schema {cls.__name__} max size {dim.size}"
                    )

            # use issubdtype to accept timedate64 with different units
            # maybe needs a flag here
            if not np.issubdtype(ds[dname].dtype, dim.dtype):
                raise DataError(
                    f"Dim {dname} actual dtype {ds[dname].dtype} "
                    f"doesn't match schema {cls.__name__} dtype {dim.dtype}"
                )

            if check_minmax and dim.minmax:
                dmin = ds[dname].min().item()
                dmax = ds[dname].max().item()
                if dim.minmax[0] > dmin or dim.minmax[1] < dmax:
                    raise DataError(
                        f"Dim {dname} actual minmax {(dmin, dmax)} "
                        f"doesn't match schema {cls.__name__} minmax {dim.minmax}"
                    )

    @classmethod
    def validate_variables(
        cls, ds: xarray.Dataset, allow_extras: bool = False, check_minmax: bool = False
    ):
        """Validates the Var fields of the schema"""
        type_hints = get_type_hints(cls)
        # check that actual variables match schema
        for vname in ds.variables:
            if vname not in type_hints:
                if allow_extras:
                    continue
                else:
                    raise DataError(
                        f"Dataset has variable {vname}, "
                        f"which is missing in strict schema {cls.__name__}"
                    )
            var = _unpack_optional(type_hints[vname])
            if isinstance(var, Var):
                if not tuple(var.dims) == ds[vname].dims:
                    raise DataError(
                        f"Variable {vname} actual dims {ds[vname].dims} "
                        f"don't match schema {cls.__name__} dims {var.dims}"
                    )
                if not np.issubdtype(ds[vname].dtype, var.dtype):
                    raise DataError(
                        f"Variable {vname} actual dtype {ds[vname].dtype} "
                        f"is not a subtype of schema {cls.__name__} dtype {var.dtype}"
                    )

            if check_minmax and var.minmax:
                vmin = ds[vname].min().item()
                vmax = ds[vname].max().item()
                if var.minmax[0] > vmin or var.minmax[1] < vmax:
                    raise DataError(
                        f"Variable {vname} actual minmax {(vmin, vmax)} "
                        f"doesn't match schema {cls.__name__} minmax {var.minmax}"
                    )

    @classmethod
    def validate_indexes(cls, ds: xarray.Dataset):
        """Validates Annotated[..., Indexed] of the schema"""
        # Indexed is added as an annotation to the field type;
        # use param include_extras to extract the metadata
        type_hints = get_type_hints(cls, include_extras=True)
        for fname, ftype in type_hints.items():
            if hasattr(ftype, "__metadata__"):
                if Indexed in ftype.__metadata__ and fname not in ds.indexes:
                    raise DataError(
                        f"Dataset is missing index for {fname}, "
                        f"which is declared as Indexed in schema {cls.__name__}"
                    )

    @classmethod
    def validate(
        cls, ds: xarray.Dataset, allow_extras: bool = False, check_minmax: bool = False
    ):
        """Validate the whole schema. Will throw DataError if xarray dataset doesn't conform"""
        cls.validate_fields_present(ds)
        cls.validate_dims(ds, allow_extras, check_minmax)
        cls.validate_variables(ds, allow_extras, check_minmax)
        cls.validate_indexes(ds)
        # Note: for attributes, we currently only check their presence,
        # and this is done in fields_present

    @classmethod
    def dims(cls) -> Dict[str, Dim]:
        """Returns the Dim fields as {name:str, info:Dim}"""
        type_hints = get_type_hints(cls)
        res = {
            fname: _unpack_optional(ftype)
            for fname, ftype in type_hints.items()
            if isinstance(_unpack_optional(ftype), Dim)
        }
        return res

    @classmethod
    def vars(cls) -> Dict[str, Var]:
        """Returns the Var fields as {name:str, info:Var}"""
        type_hints = get_type_hints(cls)
        res = {
            fname: _unpack_optional(ftype)
            for fname, ftype in type_hints.items()
            if isinstance(_unpack_optional(ftype), Var)
        }
        return res

    @classmethod
    def indexes(cls) -> Dict[str, Dim | Var]:
        """Returns the fields that were annotated as Indexed"""
        type_hints = get_type_hints(cls, include_extras=True)
        res = {
            fname: _unpack_optional(get_args(ftype)[0])
            for fname, ftype in type_hints.items()
            if hasattr(ftype, "__metadata__") and Indexed in ftype.__metadata__
        }
        return res

    @classmethod
    def attrs(cls) -> Dict[str, Attr | type[Attr]]:
        """Returns the Attr fields as {name:str, info:Attr}. Note that currently Attr is only
        a marker class with no content, therefore the info can be the Attr class directly
        instead of an object of type Attr"""
        type_hints = get_type_hints(cls)
        res = {
            fname: _unpack_optional(ftype)
            for fname, ftype in type_hints.items()
            if _unpack_optional(ftype) == Attr or isinstance(ftype, Attr)
        }
        return res

    @classmethod
    def assemble_prototype(cls):
        """Assembles a xarray prototype following the schema"""
        data_vars = {
            vname: (vtype.dims, 10 * np.random.rand(2920, 25, 53).astype(vtype.dtype))
            for vname, vtype in cls.vars().items()
        }
        coords = {
            dname: np.random.rand(dvalue.some_valid_size()).astype(dvalue.dtype)
            for dname, dvalue in cls.dims().items()
        }
        attrs = {aname: "<blank>" for aname in cls.attrs()}
        ds = xarray.Dataset(data_vars=data_vars, coords=coords, attrs=attrs)
        return ds

    @classmethod
    def add_dynamic_attribute(cls, attr_name, attr_type, attr_value=None):
        """
        Add a dynamic attribute to the class and update its type annotations.

        :param attr_name: The name of the attribute.
        :param attr_type: The type of the attribute (for type hinting).
        :param attr_value: The initial value of the attribute.
        """
        # Set the attribute on the class
        setattr(cls, attr_name, attr_value)

        # Update the class's __annotations__ with the new attribute type
        if not hasattr(cls, "__annotations__"):
            cls.__annotations__ = {}
        cls.__annotations__[attr_name] = attr_type

    @classmethod
    def remove_extras(cls, dataset: xarray.Dataset) -> xarray.Dataset:
        return dataset[cls.vars().keys()]

    @classmethod
    def translate_vars_to_stacked_ndarray(cls, dataset: xarray.Dataset) -> np.ndarray:
        """Reshape the dataset from era5-style (one variable per field)
        into the format the FCN expects it (one 'fields' variable with one
        dimension per field)"""
        arrays = [dataset[var].to_numpy() for var in cls.vars()]
        return np.stack(arrays)

    @classmethod
    def translate_vars_to_stacked_xarray(
        cls, dataset: xarray.Dataset, stackname: str, stackdimname: str
    ) -> xarray.Dataset:
        # maybe use ds.to_array(list of arrays) here?
        channel_arrays = [dataset[var] for var in cls.vars()]
        da = xarray.concat(channel_arrays, dim=stackdimname)
        # create a dataset with a single variable 'fields'
        new_ds = da.to_dataset(name=stackname)
        # add a new variable for the channel names (channel already became a dimension above)
        new_ds[stackdimname] = xarray.DataArray(
            data=[var for var in cls.vars()], dims=[stackdimname]
        ).astype("object")
        new_ds = new_ds.set_coords(
            stackdimname
        )  # probably not necessary, but doens't hurt
        return new_ds

    @classmethod
    def translate_stacked_ndarray_to_dataset(
        cls,
        array: np.ndarray,
        coords: Dict[str, Any],
        attrs: Optional[Dict[str, Any]] = None,
    ) -> xarray.Dataset:
        """Takes a numpy array of shape [num_vars, ...] and splices it into num_vars
        xarray.DataArrays of the "remaining" shape [...]. The vars are assigned in
        the order of their definition in the Schema."""
        data_vars = {}
        for i, (name, var) in enumerate(cls.vars().items()):
            data_vars[name] = (var.dims, array[i, :])

        ds = xarray.Dataset(
            data_vars=data_vars,
            coords=coords,
            attrs=attrs or {},
        )
        return ds

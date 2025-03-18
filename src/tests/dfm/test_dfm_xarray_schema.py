# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Testing the XarraySchema mechanism"""
from typing import Annotated, Optional
import pytest
import xarray
import numpy as np
from dfm.service.common.xarray_schema import XarraySchema, Dim, Var, Attr, Indexed
from dfm.service.common.exceptions import DataError


def test_valid_data_passes_validation():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float64"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    MySchema.validate(ds)


def test_optional_fields_can_be_missing_in_ds():
    """Test a schema with optional fields"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        optional_time: Optional[Dim(np.dtype("<M8[ns]"), 2920)]  # type: ignore
        air: Var(np.dtype("float64"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        optional_air: Optional[
            Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        ]
        title: Attr
        optional_title: Optional[Attr]

    # We expect no error
    MySchema.validate(ds)


def test_ds_can_have_extra_fields_when_allow_extras():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        title: Attr

    # We expect no error
    MySchema.validate(ds, allow_extras=True)


def test_unknown_dim_in_dataset_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "dimension time is missing" in str(e)


def test_unknown_var_in_dataset_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        title: Attr

    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "variable air, which is missing" in str(e)


def test_dim_missing_in_dataset_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        some_new_dim: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "dimension some_new_dim is missing" in str(e)


def test_var_missing_in_dataset_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        some_new_var: Var(np.dtype("float32"), "time", "lat", "lon")  # type: ignore
        title: Attr

    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "variable some_new_var is missing" in str(e)


def test_attr_missing_in_dataset_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr
        some_new_attr: Attr

    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "attribute some_new_attr is missing" in str(e)


def test_dim_size_can_be_range_valid_dataset_passes():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), (0, 25)), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), (53, None), minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), (None, 3000))  # type: ignore
        air: Var(np.dtype("float64"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    MySchema.validate(ds)


def test_invalid_dim_size_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 24), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "lat actual size 25" in str(e)


def test_invalid_dim_max_range_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), (0, 24)), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "lat actual size 25" in str(e)


def test_invalid_dim_min_range_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), (26, 1000)), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "lat actual size 25" in str(e)


def test_invalid_var_dimensions_order_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "lat", "lon", "time", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "Variable air actual dims" in str(e)


def test_invalid_var_dimensions_names_raises_exception():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("air_temperature")

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "typo", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    with pytest.raises(DataError) as e:
        MySchema.validate(ds)

    assert "Variable air actual dims" in str(e)


def test_schema_returns_correct_info():
    """Test xarray dataset"""

    class MySchema(XarraySchema):
        """Simple test schema"""

        lat: Annotated[Dim(np.dtype("float32"), 25), Indexed]  # type: ignore
        lon: Dim(np.dtype("float32"), 53, minmax=(10, 1000))  # type: ignore
        time: Dim(np.dtype("<M8[ns]"), 2920)  # type: ignore
        air: Var(np.dtype("float32"), "time", "lat", "lon", minmax=(100, 350))  # type: ignore
        title: Attr

    # We expect no error
    dims = MySchema.dims()
    variables = MySchema.vars()
    indexes = MySchema.indexes()
    attrs = MySchema.attrs()

    assert len(dims) == 3
    for dname, dinfo in dims.items():
        assert dname in ["lat", "lon", "time"]
        assert isinstance(dinfo, Dim)

    assert len(variables) == 1
    for vname, vinfo in variables.items():
        assert vname in ["air"]
        assert isinstance(vinfo, Var)

    assert len(indexes) == 1
    assert "lat" in indexes

    assert len(attrs) == 1
    assert "title" in attrs


def test_translate_vars_to_stacked_ndarray():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("eraint_uvz")

    class MySchema(XarraySchema):
        """Simple test schema"""

        latitude: Annotated[Dim(np.dtype("float32"), 241), Indexed]  # type: ignore
        longitude: Dim(np.dtype("float32"), 480)  # type: ignore
        level: Dim(np.dtype("int32"), 3)  # type: ignore
        month: Dim(np.dtype("int32"), 2)  # type: ignore
        # we are deliberately keeping out variable u and reordering z and v
        v: Var(np.dtype("float64"), "month", "level", "latitude", "longitude")  # type: ignore
        z: Var(np.dtype("float64"), "month", "level", "latitude", "longitude")  # type: ignore

    # select only one month, to make the test less ambiguous
    ds = ds.sel(month=[1])

    array = MySchema.translate_vars_to_stacked_ndarray(ds)
    # two variables, one month etc
    assert array.shape == (2, 1, 3, 241, 480)
    assert array[0, 0, 0, 0, 0] == ds["v"].to_numpy()[0, 0, 0, 0]
    assert array[1, 0, 0, 0, 0] == ds["z"].to_numpy()[0, 0, 0, 0]


def test_translate_vars_to_stacked_xarray():
    """Test xarray dataset"""
    ds = xarray.tutorial.load_dataset("eraint_uvz")

    class MySchema(XarraySchema):
        """Simple test schema"""

        latitude: Annotated[Dim(np.dtype("float32"), 241), Indexed]  # type: ignore
        longitude: Dim(np.dtype("float32"), 480)  # type: ignore
        level: Dim(np.dtype("int32"), 3)  # type: ignore
        month: Dim(np.dtype("int32"), 2)  # type: ignore
        # we are deliberately keeping out variable u and reordering z and v
        v: Var(np.dtype("float64"), "month", "level", "latitude", "longitude")  # type: ignore
        z: Var(np.dtype("float64"), "month", "level", "latitude", "longitude")  # type: ignore

    # select only one month, to make the test less ambiguous
    ds = ds.sel(month=[1])

    ds2 = MySchema.translate_vars_to_stacked_xarray(ds, "fields", "channel")
    print(ds2)
    assert ds2["fields"].dims == ("channel", "month", "level", "latitude", "longitude")
    assert ds2["fields"].shape == (2, 1, 3, 241, 480)
    assert ds2["channel"].size == 2


def test_translate_stacked_ndarray_to_dataset():
    """Test xarray dataset"""

    class MySchema(XarraySchema):
        """Simple test schema"""

        latitude: Annotated[Dim(np.dtype("float32"), 241), Indexed]  # type: ignore
        longitude: Dim(np.dtype("float32"), 480)  # type: ignore
        level: Dim(np.dtype("int32"), 3)  # type: ignore
        month: Dim(np.dtype("int32"), 1)  # type: ignore
        # we are deliberately keeping out variable u and reordering z and v
        v: Var(np.dtype("float64"), "month", "level", "latitude", "longitude")  # type: ignore
        z: Var(np.dtype("float64"), "month", "level", "latitude", "longitude")  # type: ignore

    array = np.stack([np.ones((1, 3, 241, 480)), np.zeros((1, 3, 241, 480))])
    assert array.shape == (2, 1, 3, 241, 480)

    ds = xarray.tutorial.load_dataset("eraint_uvz")
    coords = dict(
        latitude=ds["latitude"], longitude=ds["longitude"], level=ds["level"], month=[0]
    )
    ds2 = MySchema.translate_stacked_ndarray_to_dataset(array, coords=coords, attrs={})

    assert list(ds2.keys()) == ["v", "z"]
    assert ds2["v"].shape == (1, 3, 241, 480)
    assert ds2["v"][0, 0, 0, 0] == 1
    assert ds2["z"].shape == (1, 3, 241, 480)
    assert ds2["z"][0, 0, 0, 0] == 0

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import pytest
import numpy as np
from tests.common import MockAdapter
from dfm.api import FunctionCall
from dfm.api.xarray import ConvertToUint8 as ConvertToUint8Params
from dfm.service.execute.adapter.xarray import ConvertToUint8


from tests.common import MockDfmRequest
from tests.dfm.utils import generate_ecmwf_era5_data

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_adapter_executes():
    FunctionCall.set_allow_outside_block()
    ds = generate_ecmwf_era5_data()
    in_adapter = MockAdapter([ds])
    params = ConvertToUint8Params(
        time_dimension="time", xydims=("longitude", "latitude"), data=in_adapter.node_id
    )
    adapter = ConvertToUint8(
        MockDfmRequest(this_site="here"),
        None,  # provider # type: ignore
        None,
        params,
        in_adapter,  # type: ignore
    )
    FunctionCall.unset_allow_outside_block()
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    # min/max has been stored in attrs
    assert np.floor(result[0].attrs["data_min"].item()) == 18
    assert np.floor(result[0].attrs["data_max"].item()) == 147
    # real min/max is in int8 range
    assert result[0].to_array().min().item(0) >= 0
    assert result[0].to_array().max().item(0) <= 255
    assert result[0].dtypes == {
        "10m_u_component_of_wind": np.dtype("uint8"),
        "10m_v_component_of_wind": np.dtype("uint8"),
    }

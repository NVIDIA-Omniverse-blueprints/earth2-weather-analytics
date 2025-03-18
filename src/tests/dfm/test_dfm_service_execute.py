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
import yaml
from dfm.service.execute import Execute as ExecuteService
from dfm.api import Process
from dfm.api.dfm import Execute, GreetMe
from dfm.api.response import ValueResponse
from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_execute_can_run_simple_pipeline():
    """A very simple, but complete site"""
    with open("tests/files/simple_site_config.yaml", encoding="utf-8") as f:
        site_config = yaml.safe_load(f)

    with Process():
        with Execute(site="A") as pipeline:
            GreetMe(name="World", is_output=True)

    ex = ExecuteService(site_config, None)
    req = MockDfmRequest(this_site="here")

    async for _heartbeat in await ex.execute(req, pipeline):
        pass

    results = req.responses

    assert len(results) == 1

    assert isinstance(results[0][0].body, ValueResponse)
    assert results[0][0].body.value == "Hello World"

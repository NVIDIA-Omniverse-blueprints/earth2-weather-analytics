# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Tests for all config parsing"""
import yaml
from dfm.config import SiteConfig
from dfm.service.execute import Site
from dfm.service.execute.provider import BasicProvider, UninitializedAdapter
from dfm.api import FunctionCall
from dfm.api.dfm import GreetMe as GreetMeParams
from dfm.service.execute.adapter.dfm import GreetMe as GreetMeAdapter
from tests.common import MockDfmRequest


def test_simple_site_can_instantiate_objects():
    """A very simple, but complete site"""
    with open("tests/files/simple_site_config.yaml", encoding="utf-8") as f:
        contents = yaml.safe_load(f)
        site_config = SiteConfig.model_validate(contents)

    site = Site(site_config, None)
    dfm = site.provider("dfm")
    assert isinstance(dfm, BasicProvider)
    assert dfm.site == site
    FunctionCall.set_allow_outside_block()
    func = GreetMeParams(provider="dfm", name="Qbert")
    FunctionCall.unset_allow_outside_block()
    uninitialized_adapter = site.pre_instantiate_adapter(
        MockDfmRequest(this_site="here"), func
    )
    assert isinstance(uninitialized_adapter, UninitializedAdapter)
    assert isinstance(uninitialized_adapter.adapter_instance, GreetMeAdapter)
    initialized_adapter = uninitialized_adapter.finish_init({})
    assert uninitialized_adapter.adapter_instance == initialized_adapter

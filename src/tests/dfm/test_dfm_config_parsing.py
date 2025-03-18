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
from dfm.config import SiteConfig, ProviderConfig, AdapterConfig


def test_simple_site_config_parses_successfully_from_file():
    """A very simple, but complete site"""
    with open("tests/files/simple_site_config.yaml", encoding="utf-8") as f:
        contents = yaml.safe_load(f)
        site = SiteConfig.model_validate(contents)

    # access some deep path to make sure everything parsed
    assert isinstance(
        site.providers["dfm"].interface["dfm.api.dfm.GreetMe"], AdapterConfig
    )
    assert (
        site.providers["dfm"].interface["dfm.api.dfm.GreetMe"].adapter_class
        == "adapter.dfm.GreetMe"
    )


# =====================================
# Provider Configs
# =====================================


def test_dfm_provider_config_parses_polymorphically():
    """Make sure all configs parse in a polymorphic way"""
    contents = {
        "provider_class": "provider.BasicProvider",
        "description": "The default provider",
        "cache_storage": {"protocol": "file"},
        "interface": {},
    }
    m = ProviderConfig.model_validate(contents)
    assert m.__class__.__name__ == "BasicProvider"


# =====================================
# Adapter Configs
# =====================================


def test_greetme_adapter_config_parses_polymorphically():
    """Make sure all configs parse in a polymorphic way"""
    contents = {"adapter_class": "adapter.dfm.GreetMe", "greeting": "Hello"}
    m = AdapterConfig.model_validate(contents)
    assert m.__class__.__name__ == "GreetMe"

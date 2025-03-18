# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import yaml
from dfm.secrets import SiteSecrets
from dfm.secrets.provider import ProviderSecrets


def test_simple_site_secrets_parses_successfully_from_file():
    with open("tests/files/simple_site_secrets.yaml", encoding="utf-8") as f:
        contents = yaml.safe_load(f)
        site = SiteSecrets.model_validate(contents)

    # access some deep path to make sure everything parsed
    assert site.providers["dfm"].storage_options["my_secret"] == "abcd-1234-0000-432"  # type: ignore


def test_dfm_provider_secrets_parses_polymorphically():
    """Make sure all secret models parse successfully in a polymorphic way"""
    contents = {
        "provider_class": "provider.FsspecProvider",
        "storage_options": {"my_secret": "1245"},
    }
    m = ProviderSecrets.model_validate(contents)
    assert m.__class__.__name__ == "FsspecProvider"

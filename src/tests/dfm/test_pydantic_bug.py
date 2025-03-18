# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import sys
import pytest
from dfm.api.response._response import Response


def build_discovery_response():
    # assume we asked for advise on fields 'provider' and 'simulation' and specified a date.
    # This returned an advice tree, two possible providers with two simulations each, and in each
    # simulation the date exists but the other results in an error

    resp_d = {
        "node_id": None,
        "timestamp": "2024-10-16T19:29:14.614441Z",
        "body": {
            "api_class": "dfm.api.discovery.DiscoveryResponse",
            "advice": {
                "6626806b-7e76-498b-b786-9aac83cde6cd": {
                    "field": "provider",
                    "branches": [
                        ["ecmwf", None],
                    ],
                },
                "7674e4bf-67b3-4cc8-8c3f-8b748df55cf0": None,
                "00000000-0000-4000-8000-0000028a9f3d": None,
            },
        },
    }

    return resp_d


def test_model_rebuild_fixes_it():
    from dfm.api.discovery import BranchFieldAdvice

    BranchFieldAdvice.model_rebuild()
    r_d = build_discovery_response()
    resp_p = Response.model_validate(r_d)
    # print(f"validated response 1{resp_p} ")
    r_d = resp_p.model_dump()
    # print(f"dumped response {r_d} ")
    resp_p = Response.model_validate(r_d)
    # print(f"validated response 2{resp_p} ")
    resp_j = resp_p.model_dump_json()
    # print(f"validated response in json {resp_j} ")
    assert resp_j


def test_serialization_of_recursive_model_goes_wrong():
    # delete all dfm modules, we need to make sure that BranchFieldAdvice isn't
    # built yet
    for key in list(sys.modules.keys()):
        if key.startswith("dfm") or key.startswith("test"):
            del sys.modules[key]

    r_d = build_discovery_response()
    resp_p = Response.model_validate(r_d)
    # print(f"validated response 1{resp_p} ")
    with pytest.raises(TypeError):
        r_d = resp_p.model_dump()

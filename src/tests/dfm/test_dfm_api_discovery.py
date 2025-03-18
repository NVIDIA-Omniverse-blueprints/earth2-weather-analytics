# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import uuid
from dfm.api.discovery import (
    DiscoveryResponse,
    BranchFieldAdvice,
    SingleFieldAdvice,
    ErrorFieldAdvice,
)
from dfm.service.execute.discovery import AdvisedDateRange


def build_discovery_response() -> DiscoveryResponse:
    # assume we asked for advise on fields 'provider' and 'simulation' and specified a date.
    # This returned an advice tree, two possible providers with two simulations each, and in each
    # simulation the date exists but the other results in an error

    tree = BranchFieldAdvice(
        field="provider",
        branches=[
            (
                "eos",
                SingleFieldAdvice(
                    field="sim",
                    value=["eos_icon", "eos_graf"],
                    edge=SingleFieldAdvice(
                        field="timestamp",
                        value=AdvisedDateRange(
                            start="today", end="tomorrow"
                        ).as_pydantic_value(),
                        edge=ErrorFieldAdvice(
                            msg="The specified date does not exist in this simulation"
                        ),
                    ),
                ),
            ),
            (
                "ganon",
                BranchFieldAdvice(
                    field="sim",
                    branches=[
                        ("ganon_icon", None),
                        (
                            "ganon_graf",
                            SingleFieldAdvice(
                                field="timestamp",
                                value=AdvisedDateRange(
                                    start="today", end="tomorrow"
                                ).as_pydantic_value(),
                                edge=ErrorFieldAdvice(
                                    msg="The specified date does not exist in this simulation"
                                ),
                            ),
                        ),
                    ],
                ),
            ),
        ],
    )
    # make sure it serializes/deserializes well
    response = DiscoveryResponse(advice={uuid.uuid4(): tree})
    response = DiscoveryResponse.model_validate_json(response.model_dump_json())
    return response


def test_iterator():
    response = build_discovery_response()
    provider_field = next(iter(response.advice.values()))
    assert isinstance(provider_field, BranchFieldAdvice)

    assert provider_field.has_good_options()
    errors = provider_field.collect_error_messages()
    assert "timestamp" in errors
    assert errors["timestamp"] == set(
        ["The specified date does not exist in this simulation"]
    )

    providers = list(prov for prov in provider_field)
    # 'eos' is not a viable option, because it doesn't lead to a non-error end
    assert providers == ["ganon"]
    sim_field = provider_field.select("ganon")
    assert sim_field
    assert sim_field.has_good_options()
    errors = sim_field.collect_error_messages()
    assert "timestamp" in errors
    sims = list(sim for sim in sim_field)
    assert sims == ["ganon_icon"]

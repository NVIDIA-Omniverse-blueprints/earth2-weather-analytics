# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import List, Literal
from dfm.api._function_call import FunctionRef
from dfm.api.dfm import Execute, GreetMe
from dfm.api import FunctionCall


def test_greetme_params_serializes_polymorphically():
    params1 = GreetMe.model_validate(
        {"name": "World"}, context={"allow_outside_block": True}
    )
    json_data = params1.model_dump_json()
    params2 = GreetMe.model_validate_json(
        json_data, context={"allow_outside_block": True}
    )
    assert params1 == params2


def test_execute_params_parses_polymorphically():
    with Execute.model_validate(
        {"site": "A"}, context={"allow_outside_block": True}
    ) as exec1:
        node = GreetMe(name="World")

    json_data = exec1.model_dump_json()
    FunctionCall.set_allow_outside_block()
    exec2 = Execute.model_validate_json(
        json_data, context={"allow_outside_block": True}
    )
    FunctionCall.unset_allow_outside_block()
    assert exec1 == exec2
    assert exec2.body[node.node_id].__class__ == GreetMe


def test_list_of_adapter_gets_translated_to_uuids():
    class SomeFunction(FunctionCall, frozen=True):
        """"""

        api_class: Literal[
            "dfm.test_dfm_api_parsing.test_inputlist_params_parses_polymorphically.SomeFunction"
        ] = "dfm.test_dfm_api_parsing.test_inputlist_params_parses_polymorphically.SomeFunction"
        name: str
        inputs: List[FunctionRef]

    i1 = GreetMe.model_validate(
        {"name": "James"}, context={"allow_outside_block": True}
    )
    i2 = GreetMe.model_validate({"name": "Bond"}, context={"allow_outside_block": True})

    FunctionCall.set_allow_outside_block()
    func = SomeFunction(name="Moneypenny", inputs=[i1, i2])
    data = func.model_dump()
    inputs = data["inputs"]
    assert len(inputs) == 2
    assert i1.node_id in inputs
    assert i2.node_id in inputs
    FunctionCall.unset_allow_outside_block()

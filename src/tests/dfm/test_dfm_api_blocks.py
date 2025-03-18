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
from dfm.api import Process
from dfm.api import FunctionCall
from dfm.api.dfm import Execute, GreetMe


@pytest.fixture(autouse=True)
def cleanup_function_call_state():
    """Ensure FunctionCall state is clean before and after each test"""
    # Clean up before test
    FunctionCall.unset_allow_outside_block()
    yield
    # Clean up after test
    FunctionCall.unset_allow_outside_block()


def test_process_must_be_outermost():
    with pytest.raises(RuntimeError):
        with Execute(site="A"):
            pass


def test_process_as_outermost():
    with Process():
        pass


def test_process_simple_function():
    with Process() as p:
        greetme = GreetMe(name="World")

    assert greetme.node_id in p.execute.body


def test_process_parses_polymorphically():
    with Process() as p:
        greetme = GreetMe(name="World")

    json = p.model_dump_json()
    FunctionCall.set_allow_outside_block()
    p2 = Process.model_validate_json(json)
    FunctionCall.unset_allow_outside_block()
    assert greetme.node_id in p2.execute.body


def test_process_nested_executes():
    with Process() as p:
        with Execute(site="A") as ex1:
            greetme1 = GreetMe(name="World")
            with Execute(site="B") as ex2:
                greetme2 = GreetMe(name="World")
        greetme0 = GreetMe(name="World")

    assert greetme0.node_id in p.execute.body
    assert ex1.node_id in p.execute.body
    assert greetme1.node_id in ex1.body
    assert ex2.node_id in ex1.body
    assert greetme2.node_id in ex2.body

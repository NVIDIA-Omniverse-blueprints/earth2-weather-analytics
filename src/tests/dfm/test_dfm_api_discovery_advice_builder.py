# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Dict, List, Literal, Optional

import pytest
from collections.abc import Iterable
from dfm.common import AdviseableBaseModel
from dfm.api.discovery import Advise, SingleFieldAdvice, PartialError, ErrorFieldAdvice
from dfm.service.execute.discovery import (
    field_advisor,
    AdviceBuilder,
    AdvisedOneOf,
    AdvisedSubsetOf,
    AdvisedLiteral,
    AdvisedDict,
    AdvisedDateRange,
)


class OpenTextureStore(AdviseableBaseModel, frozen=True):
    """
    OpenTextureStore is a model for the OpenTextureStore function.
    """

    provider: str
    simulation: str
    location: str = "home"
    timestamps: List[str]
    variables: Literal["*"] | List[str]
    selection: Optional[Dict] = None


class NucleusTextureStoreAdapter:  # type: ignore
    """
    NucleusTextureStoreAdapter is an adapter for the NucleusTextureStore function.
    """

    def __init__(self, params):
        self.params = params

    @field_advisor("simulation", order=0)
    async def available_simulations(self, _value, _context):
        return AdvisedOneOf(values=["sim1", "sim2"], break_on_advice=True)

    @field_advisor("location", order=1)
    async def available_locations(self, _value, _context):
        return AdvisedOneOf(values=["loc1", "loc2"], split_on_advice=True)

    @field_advisor("timestamps", order=2)
    async def available_timestamps(self, _value, context):
        if context.get("location") == "loc1":
            return AdvisedSubsetOf(values=["ts1", "ts2", "ts3"])
        return AdvisedSubsetOf(values=["ts45", "ts46"])

    @field_advisor("variables")
    async def available_variables(self, _value, context):
        if context.get("location") == "loc1":
            return AdvisedOneOf(
                [AdvisedLiteral("*"), AdvisedSubsetOf(["temp", "height"])]
            )
        return AdvisedOneOf(
            [AdvisedLiteral("*"), AdvisedSubsetOf(["u_wind", "v_wind"])],
            split_on_advice=True,
        )

    @field_advisor("selection")
    async def valid_selections(self, _value, _context):
        none_advice = AdvisedLiteral(None)
        time_advice = AdvisedDateRange(start="today", end="tomorrow")
        dict_advice = AdvisedDict({"time": time_advice}, allow_extras=True)
        return AdvisedOneOf(values=[none_advice, dict_advice])


def roundtrip(params: OpenTextureStore) -> OpenTextureStore:
    params_json = params.model_dump_json()
    old_value = AdviseableBaseModel.set_allow_advise(True)
    params_deserialized = OpenTextureStore.model_validate_json(params_json)
    AdviseableBaseModel.set_allow_advise(old_value)

    return params_deserialized


pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_wrong_location():
    params = OpenTextureStore.as_adviseable(simulation="sim1")
    params = roundtrip(params)

    adapter = NucleusTextureStoreAdapter(params=params)
    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    # print(advice)
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.field == "location"
    assert not advice.has_good_options()
    assert (
        "Expected one of ['loc1', 'loc2'] but got home"
        in advice.collect_error_messages()["location"]
    )


@pytest.mark.asyncio
async def test_break_on_sims():
    params = OpenTextureStore.as_adviseable(simulation=Advise())
    params = roundtrip(params)

    adapter = NucleusTextureStoreAdapter(params=params)
    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    print(advice)
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.field == "simulation"
    assert advice.has_good_options()
    assert isinstance(advice, Iterable)
    options = [opt for opt in advice]  # pylint: disable=not-an-iterable
    assert "sim1" in options
    assert "sim2" in options
    with pytest.raises(PartialError):
        advice.select("sim1")


@pytest.mark.asyncio
async def test_discover_timestamps():
    params = OpenTextureStore.as_adviseable(
        simulation="sim1",
        location="loc1",
        timestamps=Advise(),
        selection={"time": "today"},
    )
    params = roundtrip(params)

    adapter = NucleusTextureStoreAdapter(params=params)
    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    print(advice)
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.field == "timestamps"
    assert isinstance(advice.value, list)
    assert set(advice.value) == set(["ts1", "ts2", "ts3"])


@pytest.mark.asyncio
async def test_discover_variables():
    params = OpenTextureStore.as_adviseable(
        simulation="sim1",
        location="loc1",
        timestamps=["ts1", "ts3"],
        variables=Advise(),
        selection={"time": "today"},
    )
    params = roundtrip(params)

    adapter = NucleusTextureStoreAdapter(params=params)
    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    print(advice)
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.field == "variables"
    assert advice.value == ["*", ["temp", "height"]]


@pytest.mark.asyncio
async def test_wrong_timestamps():
    params = OpenTextureStore.as_adviseable(
        simulation="sim1",
        location="loc1",
        timestamps=["ts1", "ts49"],
        variables=Advise(),
        selection={"time": "today"},
    )
    params = roundtrip(params)

    adapter = NucleusTextureStoreAdapter(params=params)
    builder = AdviceBuilder(adapter)  # type: ignore
    advice = await builder.generate_advice()
    print(advice)
    assert isinstance(advice, SingleFieldAdvice)
    assert advice.field == "timestamps"
    assert isinstance(advice.value, list)
    assert set(advice.value) == set(["ts1", "ts49"])
    assert advice.edge == ErrorFieldAdvice(
        msg="Expected subset of values ['ts1', 'ts2', 'ts3']"
        " but got ['ts1', 'ts49']. Value ts49 is not allowed."
    )

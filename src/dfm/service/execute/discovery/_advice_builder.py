# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# this is what is assembled by the builder class
from abc import ABC, abstractmethod
from typing import Any, List, Optional, Tuple

from pydantic import BaseModel, JsonValue

from dfm.api.discovery import (
    Advise,
    BranchFieldAdvice,
    SingleFieldAdvice,
    ErrorFieldAdvice,
    EdgeT,
    PartialFieldAdvice,
)
from dfm.service.common.exceptions import ServerError
from dfm.service.execute.adapter import Adapter

from ._advised_values import AdvisedValue, AdvisedError


class BuilderEdge(ABC):
    """
    A BuilderEdge is an edge in the builder graph.
    """

    def __init__(self, source: "BuilderNode", value: JsonValue):
        self._source = source
        if self._source:  # the root 'illegally' passes None as the source
            self._source.add_outgoing_edge(self)
        self._target: Optional["BuilderNode"] = None
        self._value = value

    @property
    def value(self) -> JsonValue:
        return self._value

    @property
    def target(self) -> Optional["BuilderNode"]:
        return self._target

    @target.setter
    def target(self, child: "BuilderNode"):
        self._target = child

    @abstractmethod
    def get(self, field: str) -> Any:
        """
        Get the value of the edge for a given field.
        """
        pass

    @abstractmethod
    def build(self) -> EdgeT:
        """
        Build the edge.
        """
        pass


class BuilderRootEdge(BuilderEdge):
    """
    A BuilderRootEdge is the root edge in the builder graph.
    """

    def __init__(self, adapter: Adapter):
        super().__init__(source=None, value=None)  # type: ignore # the root edge is special
        self._adapter = adapter

    def get(self, field: str) -> Any:
        """
        Get the value of the edge for a given field.
        """
        # Handle all the non-advise fields such that field_advisors can access them
        if not hasattr(self._adapter.params, field):
            raise ServerError(
                "Should not happen."
                f" Field {field} not found in params of adapter {self._adapter}"
            )
        value = getattr(self._adapter.params, field)
        if isinstance(value, Advise):
            raise ServerError(
                f"Asked FieldRoot for concrete value of field {field}, which is Advise()"
            )
        return value

    def build(self) -> BranchFieldAdvice | SingleFieldAdvice | None:
        """
        Build the edge.
        """
        return self._target.build() if self._target else None


class BuilderAdviceEdge(BuilderEdge):
    """
    A BuilderAdviceEdge is an edge in the builder graph that advises a value.
    """

    def __init__(self, source: "BuilderNode", advice: AdvisedValue, partial: bool):
        super().__init__(source=source, value=advice.as_pydantic_value())
        self._advice = advice
        self._partial = partial

    @property
    def partial(self) -> bool:
        return self._partial

    @property
    def target(self) -> Optional["BuilderNode"]:
        return self._target

    @target.setter
    def target(self, child: "BuilderNode"):
        if self._partial:
            raise ServerError(
                "Tried to set target node for partial edge. Should not happen."
            )
        self._target = child

    def get(self, field: str) -> Any:
        """
        Get the value of the edge for a given field.
        """
        if self._source.field == field:
            return self._advice.assumed_value()
        assert self._source
        return self._source.incoming_edge.get(field)

    def build(self) -> EdgeT:
        """
        Build the edge.
        """
        if self._partial:
            return PartialFieldAdvice()
        return self._target.build() if self._target else None


class BuilderErrorEdge(BuilderEdge):
    """
    A BuilderErrorEdge is an edge in the builder graph that represents an error.
    """

    def __init__(self, source: "BuilderNode", value: JsonValue, error: AdvisedError):
        super().__init__(source=source, value=value)
        self._error = error

    @property
    def target(self) -> Optional["BuilderNode"]:
        return self._target

    @target.setter
    def target(self, child: "BuilderNode"):
        raise ServerError("Tried to set target node on error edge. Should not happen.")

    def get(self, field: str) -> Any:
        """
        Get the value of the edge for a given field.
        """
        raise ServerError(
            f"Field {field} is an error, should not have asked for a value"
        )

    def build(self) -> EdgeT:
        """
        Build the edge.
        """
        return ErrorFieldAdvice(msg=self._error.msg)


class BuilderNode:
    """
    A BuilderNode is a node in the builder graph.
    """

    def __init__(self, field: str, incoming_edge: "BuilderEdge"):
        assert not incoming_edge.target
        self._field = field
        self._incoming_edge = incoming_edge
        self._incoming_edge.target = self
        self._outgoing_edges: List["BuilderEdge"] = []

    @property
    def field(self) -> str:
        return self._field

    @property
    def incoming_edge(self) -> BuilderEdge:
        return self._incoming_edge

    def add_outgoing_edge(self, edge: "BuilderEdge"):
        """
        Add an outgoing edge to the node.
        """
        self._outgoing_edges.append(edge)

    def build(self) -> BranchFieldAdvice | SingleFieldAdvice | None:
        """
        Build the node.
        """
        branches: List[Tuple[JsonValue, EdgeT]] = [
            (edge.value, edge.build()) for edge in self._outgoing_edges
        ]
        if len(branches) == 0:
            return None
        if len(branches) == 1:
            val, next_advice = branches[0]
            return SingleFieldAdvice(field=self._field, value=val, edge=next_advice)
        else:
            return BranchFieldAdvice(field=self._field, branches=branches)


# a helper to filter all field advisors form all adapter methods,
# in the order they should be applied
def collect_field_advisors(adapter):
    """
    Collect all field advisors from all adapter methods, in the order they should be applied.
    """
    advisors = []
    for name in dir(adapter):
        method = getattr(adapter, name)
        if hasattr(method, "field_advisor_config"):
            # print(f"found advisor {name}")
            advisors.append(method)
    advisors.sort(key=lambda m: m.field_advisor_config.order)
    return advisors


class AdviceBuilder:
    """
    An AdviceBuilder is a builder for advice.
    """

    def __init__(self, adapter: Adapter):
        """
        Initialize the AdviceBuilder.
        """
        self._adapter = adapter
        self._root = BuilderRootEdge(adapter=adapter)
        self._frontier: List[BuilderEdge] = [self._root]

    async def _validate_field(self, advisor, field: str, value: Any):
        """The advisor may or may not specialize the case when isinstance(value, Advise).
        If it does, it can indicate that the value is okay by returning Okay()
        or raise a ValidationError. If it does not specialize the isinstance(value, Advise)
        case then it just returns whatever it expects and the FieldAdvisory will
        compare the given value with what the advisor returned."""
        new_frontier: List[BuilderEdge] = []
        for incoming_edge in self._frontier:
            advice = await advisor(value, incoming_edge)
            error = advice.validate(value)
            if error:
                # user-supplied value is not good in this branch. Add a node to stop this branch
                node = BuilderNode(field, incoming_edge)
                # builder attaches itself to the node
                json_value = (
                    value.model_dump() if isinstance(value, BaseModel) else value
                )
                BuilderErrorEdge(node, json_value, AdvisedError(msg=error))
            else:
                # the user-supplied value was fine. The incoming_edge will return
                # this value from the root edge, if asked. Therefore, we don't need to add
                # a new node but just continue exploring the current edge for the next field
                new_frontier.append(incoming_edge)
        self._frontier = new_frontier

    async def _advise_field(self, advisor, field: str, value: Advise):
        new_frontier: List[BuilderEdge] = []
        for incoming_edge in self._frontier:
            node = BuilderNode(field, incoming_edge)
            advice = await advisor(value, incoming_edge)
            if isinstance(advice, AdvisedError):
                # the error edge attaches itself to the node
                BuilderErrorEdge(
                    source=node, value=advice.as_pydantic_value(), error=advice
                )
            else:
                for option in advice.iterate_advice_branches():
                    new_edge = BuilderAdviceEdge(
                        source=node, advice=option, partial=option.break_on_advice
                    )
                    if not new_edge.partial:
                        new_frontier.append(new_edge)
        self._frontier = new_frontier

    async def generate_advice(self) -> BranchFieldAdvice | SingleFieldAdvice | None:
        """Returns None if there was no advice to be given"""
        func_params = self._adapter.params
        for advisor in collect_field_advisors(self._adapter):
            field = advisor.field_advisor_config.field
            # in a full pydantic model, all fields must have a value.
            # Either they are optional and None or they are
            # specified. Only if used FunctionParams.as_advisable() a
            # field may be completely missing. We interpret
            # this as a request for advise
            value = (
                getattr(func_params, field) if hasattr(func_params, field) else Advise()
            )
            if isinstance(value, Advise):
                # Note: value is the Advise() instance. At the moment, Advise
                # doesn't contain any info, but this may change in the future.
                # Therefore, we still pass it along
                await self._advise_field(advisor, field, value)
            else:
                await self._validate_field(advisor, field, value)

            if not self._frontier:
                break

        return self._root.build()

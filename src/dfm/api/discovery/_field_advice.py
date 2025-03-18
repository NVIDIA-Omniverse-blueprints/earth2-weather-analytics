# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Any, Dict, Iterator, List, Literal, Optional, Set, Tuple, Union
from pydantic import BaseModel, JsonValue


class ErrorFieldAdvice(BaseModel):
    """Represents an edge where a field advice resulted in an error."""

    msg: str


class PartialError(Exception):
    """Raised when a path ends with a partial edge."""


class PartialFieldAdvice(BaseModel):
    """An edge represents a partial field advice if the discovery has been
    cut off to avoid combinatorial explosion. When the client encounters a partial
    field advice, it should commit to values of preceding fields and then run a
    new discovery for the remainder."""

    partial: Literal["partial"] = "partial"


EdgeT = Union[
    "BranchFieldAdvice", "SingleFieldAdvice", ErrorFieldAdvice, PartialFieldAdvice, None
]


def edge_has_target(edge: EdgeT) -> bool:
    return isinstance(edge, FieldAdvice)


def edge_get_target(edge: EdgeT) -> "FieldAdvice":
    if not isinstance(edge, FieldAdvice):
        raise ValueError("Edge does not have a target")
    return edge


def edge_has_error(edge: EdgeT) -> bool:
    return isinstance(edge, ErrorFieldAdvice)


def edge_get_error(edge: EdgeT) -> ErrorFieldAdvice:
    if not isinstance(edge, ErrorFieldAdvice):
        raise ValueError("Edge is not an error")
    return edge


def edge_is_partial(edge: EdgeT) -> bool:
    return isinstance(edge, PartialFieldAdvice)


def edge_is_good_path(edge: EdgeT) -> bool:
    if isinstance(edge, ErrorFieldAdvice):
        return False
    if isinstance(edge, FieldAdvice):
        return edge.has_good_options()
    # partial and None both (may) lead to a good outcome
    return True


def edge_collect_into(edge: EdgeT, field: str, error_map: Dict[str, Set[str]]):
    def add_error(msg: str):
        if field not in error_map:
            error_map[field] = set()
        error_map[field].add(msg)

    if edge_has_error(edge):
        add_error(edge_get_error(edge).msg)
    elif edge_has_target(edge):
        edge_get_target(edge).collect_into(error_map=error_map)


class FieldAdvice(BaseModel, ABC, Iterable, frozen=True):
    """Abstract class for BranchFieldAdvice and SingleFieldAdvice.

    This class provides the interface for field advice implementations that guide users
    through valid field value selections. It supports branching paths based on previous
    field values and validation of field value combinations.

    The class is frozen (immutable) and implements Iterable to allow iterating through
    valid field values.
    """

    @abstractmethod
    def has_good_options(self) -> bool:
        """Check if this advice contains any valid options.

        Returns:
            bool: True if there are valid value paths through this advice, False otherwise.
        """
        pass

    @abstractmethod
    def collect_into(self, error_map: Dict[str, Set[str]]):
        """Collect all error messages into the provided error map.

        Args:
            error_map: Dictionary mapping field names to sets of error messages.
                Will be modified to include any errors from this advice.
        """
        pass

    @abstractmethod
    def collect_error_messages(self) -> Dict[str, Set[str]]:
        """Get all error messages from this advice.

        Returns:
            Dict mapping field names to sets of error messages found in this advice.
        """
        pass

    @abstractmethod
    def select(self, value: JsonValue) -> Optional["FieldAdvice"]:
        """Select a value for this field and get the resulting advice.

        Args:
            value: The JSON-compatible value to select for this field.

        Returns:
            The next FieldAdvice to follow, or None if no more fields need advice.

        Raises:
            ValueError: If the selected value leads to an error state.
            PartialError: If the selected value leads to a partial state.
        """
        pass

    @abstractmethod
    def __iter__(self) -> Iterator[JsonValue]:
        """Get an iterator over the valid values for this field.

        Returns:
            Iterator yielding valid JSON-compatible values for this field.
        """
        pass


class BranchFieldAdvice(FieldAdvice, frozen=True):
    """BranchFieldAdvice is an advice for a given field which results in
    branching of the advice tree. Branches indicate that possible values of subsequent
    fields depend on the value selected for this field.

    Args:
        field: The name of the field this advice applies to
        branches: List of tuples containing (value, edge) pairs, where value is a possible
            field value and edge contains the resulting advice path

    Attributes:
        field: The name of the field this advice applies to
        branches: List of value-edge pairs representing branches
    """

    field: str
    branches: List[Tuple[JsonValue, EdgeT]]

    def has_good_options(self) -> bool:
        """Check if there are any valid paths through this advice.

        Returns:
            bool: True if at least one branch leads to a valid path, False otherwise
        """
        return any(edge_is_good_path(edge) for _, edge in self.branches)

    def collect_into(self, error_map: Dict[str, Set[str]]):
        """Collect all error messages from all branches into the provided error map.

        Args:
            error_map: Dictionary mapping field names to sets of error messages.
                Will be modified to include errors from all branches.
        """
        for _, edge in self.branches:
            edge_collect_into(edge, field=self.field, error_map=error_map)

    def collect_error_messages(self) -> Dict[str, Set[str]]:
        """Get all error messages from all branches.

        Returns:
            Dict mapping field names to sets of error messages found in any branch.
        """
        error_map = {}
        self.collect_into(error_map=error_map)
        return error_map

    def select(self, value: JsonValue) -> Optional["FieldAdvice"]:
        """Select a branch based on the provided value and get the resulting advice.

        Args:
            value: The JSON-compatible value to select a branch for

        Returns:
            The next FieldAdvice to follow from the selected branch, or None if no more fields need advice

        Raises:
            ValueError: If the selected branch leads to an error state
            PartialError: If the selected branch leads to a partial state
            StopIteration: If the value does not match any branch
        """
        it = iter(self.branches)
        val, edge = next(it)
        while val != value:
            val, edge = next(it)
        if edge_has_error(edge):
            # if you checked that there's a good option and used that value, this shouldn't happen
            raise ValueError(f"Option resulted in error {edge_get_error(edge)}")
        if edge_is_partial(edge):
            raise PartialError()
        if edge_has_target(edge):
            return edge_get_target(edge)
        return None

    def __iter__(self) -> Iterator[JsonValue]:
        """Get an iterator over the valid values across all branches.

        Returns:
            Iterator yielding only values from branches that lead to valid paths.
        """

        class ValueIterator(Iterator):
            def __init__(self, advice: BranchFieldAdvice):
                self._branches = advice.branches
                self._it = iter(advice.branches)

            def __next__(self) -> Any:
                nxt_val, nxt_edge = next(self._it)
                while not edge_is_good_path(nxt_edge):
                    nxt_val, nxt_edge = next(self._it)
                return nxt_val

        return ValueIterator(self)


class SingleFieldAdvice(FieldAdvice, frozen=True):
    """Advice for a single field that does not branch based on the chosen value.

    This class represents advice for a field where the subsequent advice path is independent
    of which value is chosen from the possible values. Unlike BranchFieldAdvice, the advice
    does not branch into different paths based on the selected value.

    Args:
        field: Name of the field this advice applies to
        value: The possible value(s) for this field. Can be a single value or list of values.
        edge: The edge containing target advice, error, or partial state information.
            Defaults to None.

    Attributes:
        field: Name of the field this advice applies to
        value: The possible value(s) for this field
        edge: Edge containing next advice state information
    """

    field: str
    value: JsonValue
    edge: EdgeT = None

    def has_good_options(self) -> bool:
        """Check if this advice has any valid options.

        Returns:
            bool: True if the edge leads to a valid path, False otherwise.
        """
        return edge_is_good_path(self.edge)

    def collect_into(self, error_map: Dict[str, Set[str]]):
        """Collect any error messages into the provided error map.

        Args:
            error_map: Dictionary mapping field names to sets of error messages to update
        """
        edge_collect_into(self.edge, field=self.field, error_map=error_map)

    def collect_error_messages(self) -> Dict[str, Set[str]]:
        """Get all error messages associated with this advice.

        Returns:
            Dict mapping field names to sets of error messages
        """
        error_map = {}
        self.collect_into(error_map=error_map)
        return error_map

    def select(self, _value: JsonValue) -> Optional["FieldAdvice"]:
        """Get the next advice state based on a selected value.

        Args:
            _value: The selected value (ignored since advice doesn't branch)

        Returns:
            The next FieldAdvice to follow, or None if no more fields need advice

        Raises:
            ValueError: If the edge leads to an error state
            PartialError: If the edge leads to a partial state
        """
        if edge_has_error(self.edge):
            raise ValueError(f"Option resulted in error {edge_get_error(self.edge)}")
        if edge_is_partial(self.edge):
            raise PartialError()
        if edge_has_target(self.edge):
            return edge_get_target(self.edge)
        return None

    def __iter__(self) -> Iterator[JsonValue]:
        """Get an iterator over the valid values for this field.

        Returns:
            Iterator yielding the possible values if the edge is valid.
            For single values, yields a one-item list containing that value.
            For iterables (except strings), yields the values directly.

        Raises:
            StopIteration: If the edge does not lead to a valid path
        """
        if not edge_is_good_path(self.edge):
            raise StopIteration()
        if isinstance(self.value, Iterable) and not isinstance(self.value, str):
            return iter(self.value)
        return iter([self.value])

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
from typing import Any, Dict, Iterator, List, Optional
from collections.abc import Iterable
from pydantic import JsonValue

from dfm.service.common.exceptions import ServerError


class AdvisedValue(ABC):
    """Subclasses of AdvisedValue is what field_advisor method decorators return"""

    def __init__(self, break_on_advice=False):
        self._break_on_advice = break_on_advice

    @property
    def break_on_advice(self) -> bool:
        return self._break_on_advice

    @abstractmethod
    def assumed_value(self) -> Any:
        """Returns some assumed value that subsequent fields use to produce their
        advice. Only used if the user didn't provide an actual value"""

    @abstractmethod
    def validate(self, value: Any) -> Optional[str]:
        pass

    @abstractmethod
    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        pass

    @abstractmethod
    def as_pydantic_value(self) -> JsonValue:
        pass


class AdvisedError(AdvisedValue):
    """
    An AdvisedError is an error that is advised.
    """

    def __init__(self, msg: str):
        super().__init__()
        self._msg = msg

    @property
    def msg(self) -> str:
        return self._msg

    def assumed_value(self) -> Any:
        raise ServerError("Tried to get value from error")

    def validate(self, value: Any) -> Optional[str]:
        return self._msg

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        raise ServerError("Tried to get iterate branches from error")

    def as_pydantic_value(self) -> JsonValue:
        raise ServerError("Tried to get JsonValue from error")

    def __repr__(self) -> str:
        return f"AdvisedError({self._msg})"


class AdvisedLiteral(AdvisedValue):
    """
    An AdvisedLiteral is a literal value that is advised.
    """

    def __init__(self, value: JsonValue, break_on_advice: bool = False):
        super().__init__(break_on_advice=break_on_advice)
        self._value = value

    def assumed_value(self) -> Any:
        return self._value

    def validate(self, value: Any) -> Optional[str]:
        if not self._value == value:
            return f"Expected value {self._value} but got {value}"
        return None

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        yield self

    def as_pydantic_value(self) -> JsonValue:
        return self._value

    def __repr__(self) -> str:
        return f"Literal({self._value})"


class AdvisedDict(AdvisedValue):
    """
    An AdvisedDict is a dictionary that is advised.
    """

    def __init__(
        self,
        dictionary: Dict[str, JsonValue | AdvisedValue],
        allow_extras: bool = False,
        break_on_advice: bool = False,
    ):
        super().__init__(break_on_advice=break_on_advice)
        self._dictionary = dictionary
        self._allow_extras = allow_extras

    def assumed_value(self) -> Any:
        return self._dictionary

    def validate(self, value: Any) -> Optional[str]:
        if not isinstance(value, dict):
            return f"Expected dictionary but got {value}"
        for k, expected_value in self._dictionary.items():
            if k not in value:
                return f"Expected key {k} but got {value}"
            if isinstance(expected_value, AdvisedValue):
                expected_value.validate(value[k])
            elif value[k] is not expected_value:
                return f"Expected value {expected_value} for key {k} but got {value[k]}"
        if not self._allow_extras and self._dictionary.keys() is not value.keys():
            return (
                f"Expected exact keys {self._dictionary.keys()} but got {value.keys()}"
            )
        return None

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        yield self

    def as_pydantic_value(self) -> JsonValue:
        result: Dict[str, JsonValue] = {}
        for k, v in self._dictionary.items():
            if isinstance(v, AdvisedValue):
                result[k] = v.as_pydantic_value()
            else:
                result[k] = v
        return result

    def __repr__(self) -> str:
        return f"Dict({str(self._dictionary)})"


class AdvisedDateRange(AdvisedValue):
    """
    An AdvisedDateRange is a date range that is advised.
    """

    def __init__(self, start: str, end: str, break_on_advice: bool = False):
        super().__init__(break_on_advice=break_on_advice)
        self._start = start
        self._end = end

    def assumed_value(self) -> Any:
        return self._start

    def validate(self, value: Any) -> Optional[str]:
        if not (self._start <= value and self._end >= value):
            return f"Expected date range in {self._start}..{self._end} but got {value}"
        return None

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        yield self

    def as_pydantic_value(self) -> JsonValue:
        return {"startdate": self._start, "enddate": self._end, "timeinterval": "???"}

    def __repr__(self) -> str:
        return f"DateRange({str(self._start)}, {str(self._end)})"


class AdvisedOneOf(AdvisedValue):
    """
    An AdvisedOneOf is a one of that is advised.
    """

    def __init__(
        self,
        values: List[JsonValue | AdvisedValue],
        break_on_advice: bool = False,
        split_on_advice: bool = False,
    ):
        super().__init__(break_on_advice=break_on_advice)
        self._values = values
        self._split_on_advice = split_on_advice

    def assumed_value(self) -> Any:
        return self._values[0]

    def validate(self, value: Any) -> Optional[str]:
        for possible_val in self._values:
            if isinstance(possible_val, AdvisedValue):
                msg = possible_val.validate(value)
                if msg is None:
                    # possible_val accepts the value as correct, we accept it
                    return None
            elif possible_val == value:
                # possible_val is a JsonValue and it's equal to the value, we accept it
                return None
        # didn't accept value
        return f"Expected one of {self._values} but got {value}"

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        if self._split_on_advice:
            for o in self._values:
                if isinstance(o, AdvisedValue):
                    yield AdvisedLiteral(o.as_pydantic_value(), self._break_on_advice)
                else:
                    yield AdvisedLiteral(o, self._break_on_advice)
        else:
            yield self

    def as_pydantic_value(self) -> JsonValue:
        result: List[JsonValue] = []
        for v in self._values:
            if isinstance(v, AdvisedValue):
                result.append(v.as_pydantic_value())
            else:
                result.append(v)
        return result

    def __repr__(self) -> str:
        return f"OneOf({','.join([str(val) for val in self._values])})"


class AdvisedSubsetOf(AdvisedValue):
    """
    An AdvisedSubsetOf is a subset of that is advised.
    """

    def __init__(
        self,
        values: List[JsonValue | AdvisedValue],
        break_on_advice: bool = False,
        split_on_advice: bool = False,
    ):
        super().__init__(break_on_advice=break_on_advice)
        self._values = values
        self._split_on_advice = split_on_advice

    def assumed_value(self) -> Any:
        return self._values

    def validate(self, value: Any) -> Optional[str]:
        if isinstance(value, Iterable):
            values = value
        else:
            values = [value]
        # each val must be allowed
        for val in values:
            is_okay = False
            for possible_val in self._values:
                if isinstance(possible_val, AdvisedValue):
                    msg = possible_val.validate(value)
                    if msg is None:
                        # possible_val accepts the value as correct, we accept it
                        is_okay = True
                        break
                elif possible_val == val:
                    # possible_val is a JsonValue and it's equal to the value, we accept it
                    is_okay = True
                    break
            if not is_okay:
                return (
                    f"Expected subset of values {self._values}"
                    f" but got {values}. Value {val} is not allowed."
                )
        return None

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        if self._split_on_advice:
            for o in self._values:
                if isinstance(o, AdvisedValue):
                    yield AdvisedLiteral(o.as_pydantic_value(), self._break_on_advice)
                else:
                    yield AdvisedLiteral(o, self._break_on_advice)
        else:
            yield self

    def as_pydantic_value(self) -> JsonValue:
        result: List[JsonValue] = []
        for v in self._values:
            if isinstance(v, AdvisedValue):
                result.append(v.as_pydantic_value())
            else:
                result.append(v)
        return result

    def __repr__(self) -> str:
        return f"SubsetOf({','.join([str(val) for val in self._values])})"


class Okay(AdvisedValue):
    """Can be returned by a field_advisor method during validation
    to indicate a simple 'the value is okay'"""

    def __init__(self):
        super().__init__()

    def assumed_value(self) -> Any:
        raise ServerError("This should not have happened.")

    def validate(self, value: Any) -> Optional[str]:
        return None

    def iterate_advice_branches(self) -> Iterator["AdvisedValue"]:
        yield self

    def as_pydantic_value(self) -> JsonValue:
        raise ServerError(
            "Tried to get pydantic value from advised Okay(),"
            " which should only be used during validation"
        )

    def __repr__(self) -> str:
        return "ValueWasOkay"

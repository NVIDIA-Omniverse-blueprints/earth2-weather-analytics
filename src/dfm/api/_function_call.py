# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""The base class for all Function models."""
from typing import Any, Literal
import uuid

from pydantic import UUID4, ConfigDict, Field, field_validator
from ..common import PolymorphicBaseModel


class FunctionCall(PolymorphicBaseModel, frozen=True):
    """Base class for all DFM function models.

    This class provides the core functionality for defining DFM functions that can be executed
    in a pipeline. It handles function registration, node identification, and pipeline integration.

    When implementing a new function model:
    1. Inherit from this class
    2. Add an import to the __init__.py
    3. Use FunctionRef as the type for input fields that reference other functions

    The class uses PolymorphicBaseModel to enable polymorphic serialization/deserialization
    via an 'api_class' field that identifies the concrete class.

    Args:
        api_class: Fully qualified name of the concrete function class.
            Must match the actual class name. Used for polymorphic deserialization.
        provider: Provider that should execute this function. Defaults to "dfm".
        node_id: Unique identifier for this node in the pipeline.
            Auto-generated if not provided.
        is_output: Whether this function's result should be returned to client.
            Defaults to False.
        force_compute: Whether to force recomputation even if cached results exist.
            Defaults to False.

    Class Methods:
        api_key: Get the api_class literal value for this function type
        set_allow_outside_block: Configure whether functions can be created outside a Block
        unset_allow_outside_block: Disable creation of functions outside a Block

    The class automatically adds new function instances to the current Block context
    unless specifically allowed to exist outside via set_allow_outside_block().
    """

    model_config = ConfigDict(extra="forbid")

    api_class: Literal["ABSTRACT"]
    provider: str = "dfm"
    node_id: UUID4 = Field(default_factory=uuid.uuid4)
    is_output: bool = False
    force_compute: bool = False  # if true, ignore the caches

    @classmethod
    def api_key(cls) -> str:
        """Get the api_class literal value for this function type.

        Returns:
            The api_class literal defined in the model fields
        """
        return cls.model_fields["api_class"].default

    @classmethod
    def set_allow_outside_block(cls, val: bool = True) -> bool:
        """Configure whether functions can be created outside a Block context.

        Args:
            val: If True, allows functions outside Block. Defaults to True.

        Returns:
            Previous allow_outside_block setting
        """
        before = hasattr(cls, "_allow_outside_block") and getattr(
            cls, "_allow_outside_block"
        )
        if val:
            setattr(cls, "_allow_outside_block", val)
        elif hasattr(cls, "_allow_outside_block"):  # Only try to delete if it exists
            delattr(cls, "_allow_outside_block")
        return before

    @classmethod
    def unset_allow_outside_block(cls) -> bool:
        """Disable creation of functions outside a Block context.

        Returns:
            Previous allow_outside_block setting
        """
        return cls.set_allow_outside_block(False)

    def model_post_init(self, __context):
        """Post-initialization hook that adds function to current Block.

        Raises:
            RuntimeError: If no Block context exists and outside blocks not allowed
        """
        # import here to break circular dependency
        from ._block import Block  # pylint: disable=import-outside-toplevel

        try:
            Block.get_block().add_to_body(self)
        except RuntimeError as e:
            if hasattr(FunctionCall, "_allow_outside_block") or (
                __context
                and "allow_outside_block" in __context
                and __context["allow_outside_block"]
            ):
                return
            raise e

    @field_validator("*")
    @classmethod
    def rewrite_functioncall_to_uuid(cls, v: Any) -> Any:
        """Validator that converts FunctionCall references to their node_ids.

        Args:
            v: Value to validate/convert

        Returns:
            Original value with any FunctionCalls replaced by their node_ids
        """
        if isinstance(v, FunctionCall):
            return v.node_id
        if isinstance(v, list):
            # rewrite all FunctionCall objects to their node_id
            return [e.node_id if isinstance(e, FunctionCall) else e for e in v]
        return v


FunctionRef = FunctionCall | UUID4

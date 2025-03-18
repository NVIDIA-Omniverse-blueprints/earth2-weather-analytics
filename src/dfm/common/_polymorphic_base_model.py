# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""A BaseModel extension adding automatic polymorphism to Pydantic."""
import importlib
from typing import Any, Tuple
from pydantic import BaseModel, model_validator, model_serializer
from pydantic_core import PydanticCustomError


class PolymorphicBaseModel(BaseModel, frozen=True):
    """
    Pydantic does not support polymorphism out of the box, which makes
    this approach necessary. That is, if a subclass of Bar, Foo(Bar), is
    deserialized json = Foo().model_dump_json() and then reserialized
    as the base class: model = Bar().model_validate_json(json) you actually
    get a Bar object back, not the original foo.

    The PolymorphicBaseModel will check if the data contains a 'api_class' field during
    model validation. If yes, the api_class value will be interpreted as the actual class name.
    Pydantic doesn't support this, and when de-serializing a field declared as List[Function]
    Pydantic will instantiate actual Function objects, instead of the correct subclass.
    """

    @classmethod
    def _discriminator_name(cls) -> str:
        return "api_class"

    @classmethod
    def _rewrite_discriminator_value_to_model_class(
        cls, module_path: str, class_name: str
    ) -> Tuple[str, str]:
        return (module_path, class_name)

    @model_validator(mode="wrap")  # type: ignore
    @classmethod
    def _replace_with_tagged_class(cls, values, handler, _info) -> Any:
        """When using polymorphic base models with a discriminator tag, a user model will
        often not specify the concrete leaf class as the type, but use an abstract base model.
        For example, a "Script" BaseModel may have a field funcs: List[Function] and would expect
        that this array contains not actual Function objects, but the correct subclasses
        of Function. However, pydantic would instantiate actual Function objects in this list,
        instead of the correct subclasses.
        This model_validator runs in this case on the Function class that Pydantic would try
        to instantiate and checks if there is a type tag in the data. If yes, it will get the
        Python BaseModel class from this tag and run model_validate on there.
        """
        if not isinstance(values, dict):
            return handler(values)

        # this happens when a user doesn't explicitly specify the api key (which he shouldn't)
        # We simply let Pydantic take care of this; we only do polymorphic stuff when the api
        # key is provided explicitly
        if cls._discriminator_name() not in values:
            return handler(values)

        try:
            module_path, class_name = values[cls._discriminator_name()].rsplit(".", 1)
            # give the class a chance to rewrite the classname written in the PydanticModel
            module_path, class_name = cls._rewrite_discriminator_value_to_model_class(
                module_path, class_name
            )
        except ValueError as ex:
            raise PydanticCustomError(
                "PolymorphicBaseModel",
                f"PolymorphicBaseModel: The discriminator literal {cls._discriminator_name()} "
                "doesn't look like a module path",  # type: ignore
            ) from ex

        module = importlib.import_module(module_path)

        try:
            the_class = getattr(module, class_name)
            if the_class == cls:
                return handler(values)
            else:
                return the_class.model_validate(values)
        except AttributeError as ex:
            raise PydanticCustomError(
                "PolymorphicBaseModel-object",
                "PolymorphicBaseModel: Could not instantiate "
                f"class {module_path}.{class_name}",  # type: ignore
            ) from ex

    @model_serializer(mode="wrap", when_used="always")
    def serialize_model(self, _handler, _info) -> dict[str, Any]:
        """Pydantic serializes a field like List[FunctionParam] as actual
        FunctionParam objects, not as the concrete subclass, missing out fields from the
        subclass. This model serializer adds back those missing fields"""
        # the pydantic handler will only serialize the base class fields
        d = {field: getattr(self, field) for field in self.model_fields}
        return d

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Literal
from pydantic import BaseModel, field_validator


class Advise(BaseModel):
    """This is the marker attached to FunctionCall objects to request advice for fields"""

    advise: Literal["Field"] = "Field"


class AdviseableBaseModel(BaseModel, frozen=True):
    """An AdviseableBaseModel is a Pydantic model (usually a FunctionCall) for which
    any field can be set to Advise(), even if the Pydantic model technically doesn't
    allow this in its schema. Fields are set to Advise() by the client to run discovery
    (see there)."""

    @classmethod
    def is_advise_allowed(cls) -> bool:
        """Check if advise is allowed for this model.

        Returns:
            True if advise is allowed, False otherwise
        """
        return hasattr(cls, "_allow_advise") and getattr(cls, "_allow_advise")

    @classmethod
    def set_allow_advise(cls, val: bool = True) -> bool:
        """Configure whether advise is allowed for this model.

        Args:
            val: If True, allows advise. Defaults to True.

        Returns:
            Previous allow_advise setting
        """
        before = hasattr(cls, "_allow_advise") and getattr(cls, "_allow_advise")
        if val:
            setattr(cls, "_allow_advise", val)
        else:
            if hasattr(cls, "_allow_advise"):
                delattr(cls, "_allow_advise")
        return before

    @classmethod
    def unset_allow_advise(cls) -> bool:
        """Disable advise for this model.

        Returns:
            Previous allow_advise setting
        """
        return cls.set_allow_advise(False)

    @classmethod
    def as_adviseable(cls, **kwargs):
        """as_adviesable returns an instance that has all validation turned off. This allows
        the user to set arbitrary fields to Advise.
        This method will set all fields that are not passed as kwargs and that don't have
        default values to Advise()"""
        # we instantiate the model twice, to work around pydantic validation errors when
        # calling model dump. The first time, we do it to get all the default values
        template = cls.model_construct(**kwargs)
        fields = {}
        for field in cls.model_fields:
            if hasattr(template, field):
                fields[field] = getattr(template, field)
            else:
                fields[field] = Advise()
        instance = cls.model_construct(**fields)
        return instance

    @field_validator("*", mode="wrap")
    @classmethod
    def deserialize_advise(cls, value, handler, info):
        """During discovery, we turn off model validation and allow the user to set
        any field to Advise, which is against the pydantic validation (which is fine
        during discovery). On the client side, as_adviseable() is used to create such an
        instance that allows for arbitrary values in each field (no validation).
        On the server-side, we want to deserialize this (technically wrong) json and add
        the Advise instances again, but we want to do this in a way that allows for nested
        pydantic models to be deserialized. This is done in this method. We wrap all
        fields and if a field is an Advise, we re-create the advise. Otherwise
        we call the original handler.
        Create like
        MyModel.as_adviseable(
            some_field=Advise(),
            some_val=42,
            other_field=OtherModel.as_asviseable(foo=Advise())
        )
        Deserialize like
        MyModel.model_validate(od.model_dump(), context={"as_adviseable": True})
        """
        # from https://github.com/pydantic/pydantic/issues/8084
        if (
            cls.is_advise_allowed()
            and value
            and isinstance(value, dict)
            and "advise" in value
        ):
            return Advise.model_validate(value)
        else:
            return handler(value)

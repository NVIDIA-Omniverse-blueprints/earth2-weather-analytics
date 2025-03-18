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
import pydantic
from ._response_body import ResponseBody


class ValueResponse(ResponseBody, frozen=True):
    """
    ValueResponse encapsulate the output returned by a FunctionCall on a site to the client.
    ValueResponses are created when the is_output argument is set to True in a FunctionCall.
    The ValueResponse will contain the json-encodable result of the FunctionCall and needs
    to be unpacked accordingly. E.g. if the expected result is a pydantic model MyModel
    you would do something like MyModel.model_validate(value). Usually, the type of the
    returned value is known because the node_id in the response indicates which function
    call produced this ValueResponse. However, in some cases it can be useful to inspect
    the json value, for example to extract an 'api_class' field.

    Args:
        value: The json value (string, int, dict, list, ...) as the function's result.
    """

    api_class: Literal["dfm.api.response.ValueResponse"] = (
        "dfm.api.response.ValueResponse"
    )
    value: pydantic.JsonValue

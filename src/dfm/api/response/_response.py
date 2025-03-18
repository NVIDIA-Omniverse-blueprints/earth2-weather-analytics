# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import datetime
from typing import Optional
from functools import partial
from pydantic import BaseModel, UUID4, Field
from ._response_body import ResponseBody

# circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._value_response import ValueResponse
    from ._status_response import StatusResponse
    from ._error_response import ErrorResponse
    from ._heartbeat_response import HeartbeatResponse
else:
    ValueResponse = object
    StatusResponse = object
    ErrorResponse = object
    HeartbeatResponse = object


class Response(BaseModel, frozen=True):
    """
    Response objects are returned by the Process service when the client
    polls for responses. The Response wraps its payload, the ResponseBody.

    Args:
        node_id: The node_id (aka FunctionCall) in the pipeline script that belongs
                to this Response. Some Responses, such as general status messages,
                may not be associated with a specific node_id, in which case this field
                is None.
        timestamp: The timestamp when this Response object has been created on the site.
        body: The payload ResponseBody object.
    """

    node_id: Optional[UUID4] = None
    timestamp: datetime.datetime = Field(
        default_factory=partial(datetime.datetime.now, datetime.timezone.utc)
    )
    body: ResponseBody

    def is_value_response(self) -> bool:
        """
        Check if this response contains a value response body.

        Returns:
            True if the response body is a value response, False otherwise.
        """
        # NOTE: above, we redefine the type to be object to avoid circular import
        # Therefore we reimport here
        from ._value_response import ValueResponse

        return isinstance(self.body, ValueResponse)

    def value_response(self) -> ValueResponse:
        """
        Get the value response body.

        Returns:
            The value response body.

        Raises:
            ValueError: If the response body is not a value response.
        """
        if self.is_value_response():
            return self.body  # type: ignore
        raise ValueError(
            "Response body is not a value response"
            f" but of type {self.body.__class__.__name__}"
        )

    def is_status_response(self) -> bool:
        """
        Check if this response contains a status response body.

        Returns:
            True if the response body is a status response, False otherwise.
        """
        # NOTE: above, we redefine the type to be object to avoid circular import
        # Therefore we reimport here
        from ._status_response import StatusResponse

        return isinstance(self.body, StatusResponse)

    def status_response(self) -> StatusResponse:
        """
        Get the status response body.

        Returns:
            The status response body.

        Raises:
            ValueError: If the response body is not a status response.
        """
        if self.is_status_response():
            return self.body  # type: ignore
        raise ValueError(
            "Response body is not a status response"
            f" but of type {self.body.__class__.__name__}"
        )

    def is_error_response(self) -> bool:
        """
        Check if this response contains an error response body.

        Returns:
            True if the response body is an error response, False otherwise.
        """
        # NOTE: above, we redefine the type to be object to avoid circular import
        # Therefore we reimport here
        from ._error_response import ErrorResponse

        return isinstance(self.body, ErrorResponse)

    def error_response(self) -> ErrorResponse:
        """
        Get the error response body.

        Returns:
            The error response body.

        Raises:
            ValueError: If the response body is not an error response.
        """
        # NOTE: above, we redefine the type to be object to avoid circular import
        # Therefore we reimport here
        if self.is_error_response():
            return self.body  # type: ignore
        raise ValueError(
            "Response body is not an error response"
            f" but of type {self.body.__class__.__name__}"
        )

    def is_heartbeat_response(self) -> bool:
        """
        Check if this response contains a heartbeat response body.

        Returns:
            True if the response body is a heartbeat response, False otherwise.
        """
        # NOTE: above, we redefine the type to be object to avoid circular import
        # Therefore we cannot use isinstance here!
        from ._heartbeat_response import HeartbeatResponse

        return isinstance(self.body, HeartbeatResponse)

    def heartbeat_response(self) -> HeartbeatResponse:
        """
        Get the heartbeat response body.

        Returns:
            The heartbeat response body.

        Raises:
            ValueError: If the response body is not a heartbeat response.
        """
        if self.is_heartbeat_response():
            return self.body  # type: ignore
        raise ValueError(
            "Response body is not a heartbeat response"
            f" but of type {self.body.__class__.__name__}"
        )

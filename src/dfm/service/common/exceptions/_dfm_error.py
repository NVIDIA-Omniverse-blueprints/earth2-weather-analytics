# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Collection of Exceptions that the dfm server codes throw. The exceptions are http inspired
but are supposed to be transport-independent, e.g., if a service communicates via
gRPC. The service layer (e.g. the FastAPI server or gRPC frontend) are expected to catch
those DfmErrors and re-throw as the corresponding transport-specific exception."""
from abc import ABC
import traceback

from dfm.api.response import ErrorResponse


class DfmError(Exception, ABC):
    """The abstract base class for all DfmErrors"""

    _http_status_code: int

    def __init__(self, message: str | Exception, http_status_code: int):
        super().__init__(message)
        self._message = str(message)
        self._http_status_code = http_status_code

    @property
    def message(self):
        return self._message

    @property
    def http_status_code(self):
        return self._http_status_code

    @property
    def traceback(self) -> str:
        return "".join(traceback.format_exception(self))

    def as_error_response(self) -> ErrorResponse:
        return ErrorResponse(
            http_status_code=self.http_status_code,
            message=self.message,
            traceback=self.traceback,
        )

    @classmethod
    def error_response_from_exception(cls, ex: Exception) -> ErrorResponse:
        return ErrorResponse(
            http_status_code=500,
            message=str(ex),
            traceback="".join(traceback.format_exception(ex)),
        )

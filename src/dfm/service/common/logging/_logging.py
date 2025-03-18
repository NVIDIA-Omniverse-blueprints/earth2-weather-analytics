#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


"""
Common logging infrastructure
"""

import datetime
import logging
import os
import textwrap
import uuid

from typing import Any

import json_log_formatter

from dfm.service.common.request import DfmRequest


class DfmJSONFormatter(json_log_formatter.JSONFormatter):
    """
    Represents log formatter that can augment log records with additional data
    """

    def json_record(self, message: str, extra: dict, record: logging.LogRecord) -> dict:
        """
        Process log record
        """
        extra["message"] = message

        # Include builtins
        extra["level"] = record.levelname
        extra["name"] = record.name
        # Log time in ISO-8601 with time zone information
        extra["time"] = (
            datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat()
        )

        if record.exc_info:
            extra["exc_info"] = self.formatException(record.exc_info)

        return extra


_FORMAT = (
    "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)

# We keep formatters and json handler around since they have no state
# and can be reused by different modules. It also simplifies managing
# many loggers when we do request id logging.
_JSON_FORMATTER = DfmJSONFormatter(_FORMAT)
_JSON_HANDLER = logging.StreamHandler()
_JSON_HANDLER.setFormatter(_JSON_FORMATTER)

_CONSOLE_FORMATTER = logging.Formatter(_FORMAT)
_CONSOLE_HANDLER = logging.StreamHandler()
_CONSOLE_HANDLER.setFormatter(_CONSOLE_FORMATTER)

# Maximum length of messages that we want to shorten
_SHORT_LENGTH = 120


def getLogger(
    name: str | None = None, request: str | DfmRequest | uuid.UUID | None = None
) -> logging.LoggerAdapter:
    """
    Create a logger object and enable JSON logging on it if JSON logging is enabled
    """
    logger = logging.getLogger(name)
    level_string = os.environ.get("SERVICE_LOGGING_LEVEL", "info")
    try:
        level = getattr(logging, level_string.upper())
    except AttributeError:
        logging.error(
            "Unknown log level set by SERVICE_LOGGING_LEVEL: %s, setting INFO",
            level_string,
        )
        level = logging.INFO
    logger.setLevel(level)

    logger.propagate = False
    if os.environ.get("SERVICE_LOGGING_ENABLE_JSON", "false") == "true":
        # logger class detects if a particular handler is already set, so we can safely always call addHandler
        logger.addHandler(_JSON_HANDLER)
    else:
        logger.addHandler(_CONSOLE_HANDLER)

    extras = None
    if isinstance(request, str):
        extras = {"request_id": request}
    elif isinstance(request, DfmRequest):
        extras = {"request_id": str(request.request_id)}
    elif isinstance(request, uuid.UUID):
        extras = {"request_id": str(request)}

    adapter = logging.LoggerAdapter(logger, extras)

    return adapter


def shorten(s: Any) -> str:
    return textwrap.shorten(str(s), _SHORT_LENGTH)

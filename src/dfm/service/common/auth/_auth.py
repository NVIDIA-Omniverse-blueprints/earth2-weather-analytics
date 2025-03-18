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
Common tools for authentication and authorization
"""

import os

from abc import ABC, abstractmethod
from enum import Enum
from logging import LoggerAdapter

from dfm.service.common.logging import getLogger


class AuthMethod(Enum):
    """
    Authentication method.
    """

    NONE = "none"
    API_KEY = "api_key"


"""
The default authentication method. Should be set
to the most secure method we have implemented.
"""
DEFAULT_AUTH_METHOD = AuthMethod.API_KEY
"""
Authentication method is chosen based on the value of
env variable which name is specified here
"""
AUTH_METHOD_ENV = "DFM_AUTH_METHOD"


class AuthBase(ABC):
    """
    Base class for all authentication methods.
    """

    def __init__(self, auth_method: AuthMethod) -> None:
        self._method = auth_method

    @property
    def method(self):
        return self._method

    @property
    @abstractmethod
    def secret(self) -> str: ...

    @abstractmethod
    def authenticate(self, user_secret: str | None) -> bool: ...


class AuthNone(AuthBase):
    """
    No authentication.
    """

    def __init__(self) -> None:
        super().__init__(AuthMethod.NONE)

    def authenticate(self, user_secret: str | None = None) -> bool:
        return True

    @property
    def secret(self):
        return None


class AuthApiKey(AuthBase):
    """
    API key authentication - not very secure, but good for development
    and demo setups.
    """

    AUTH_API_KEY_ENV = "DFM_AUTH_API_KEY"
    AUTH_API_KEY_MIN_LENGTH = 32

    def __init__(self) -> None:
        super().__init__(AuthMethod.API_KEY)
        # Let's use some incorrect key as a default - just to make sure
        api_key = os.environ.get(AuthApiKey.AUTH_API_KEY_ENV, None)
        if not api_key:
            # Don't allow empty key
            raise RuntimeError(f"{AuthApiKey.AUTH_API_KEY_ENV} not set or empty")
        if len(api_key) < AuthApiKey.AUTH_API_KEY_MIN_LENGTH:
            # Require some secure api key. It can be easily generated using pwgen tool
            # (at least on Linux):
            # pwgen -s 32 1
            raise ValueError(
                f"API key length must be at least {AuthApiKey.AUTH_API_KEY_MIN_LENGTH} characters"
            )
        self._api_key = api_key

    def authenticate(self, user_secret: str | None = None) -> bool:
        if not user_secret:
            return False
        if self._api_key == user_secret:
            return True
        return False

    @property
    def secret(self):
        return self._api_key


def get_auth(logger: LoggerAdapter = getLogger("auth")) -> AuthBase:
    """
    Get the authentication method based on the environment variable.

    Args:
        logger: Logger adapter to use for logging.

    Returns:
        Authentication method.
    """
    method_env = os.environ.get(AUTH_METHOD_ENV)
    try:
        # Try to convert string to AuthMethod.
        # If that fails - an unsupported or wrong method
        # has been provided, so we need to use the default.
        method = AuthMethod(method_env)
    except ValueError:
        logger.warning(
            "Unknown or no authentication method provided, defaulting to %s",
            DEFAULT_AUTH_METHOD,
        )
        method = DEFAULT_AUTH_METHOD

    if method == AuthMethod.NONE:
        return AuthNone()
    elif method == AuthMethod.API_KEY:
        return AuthApiKey()
    raise RuntimeError("Unknown or unsupported authentication method: %s", str(method))

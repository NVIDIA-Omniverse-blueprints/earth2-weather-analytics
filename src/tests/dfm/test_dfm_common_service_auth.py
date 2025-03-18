# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import os
from unittest.mock import patch
from dfm.service.common.auth import get_auth
from dfm.service.common.auth._auth import (
    DEFAULT_AUTH_METHOD,
    AUTH_METHOD_ENV,
    AuthMethod,
    AuthNone,
    AuthApiKey,
)


@patch.dict(os.environ, {AuthApiKey.AUTH_API_KEY_ENV: "a" * 32}, clear=True)
def test_get_auth_default_no_var():
    """
    Check that we select the expected authentication method if no
    env variable is configured
    """
    auth = get_auth()
    assert DEFAULT_AUTH_METHOD == AuthMethod.API_KEY
    assert auth.method == DEFAULT_AUTH_METHOD
    assert isinstance(auth, AuthApiKey)


@patch.dict(
    os.environ,
    {
        AUTH_METHOD_ENV: "invalid",
        AuthApiKey.AUTH_API_KEY_ENV: "a" * 32,
    },
    clear=True,
)
def test_get_auth_default_invalid_var():
    """
    Check that we select the expected authentication method if
    invalid env variable value is provided
    """
    auth = get_auth()
    assert DEFAULT_AUTH_METHOD == AuthMethod.API_KEY
    assert auth.method == DEFAULT_AUTH_METHOD
    assert isinstance(auth, AuthApiKey)


@patch.dict(
    os.environ,
    {
        AUTH_METHOD_ENV: "none",
    },
    clear=True,
)
def test_get_auth_method_none():
    """
    Check that we select the expected authentication method - none
    """
    auth = get_auth()
    assert auth.method == AuthMethod.NONE
    assert isinstance(auth, AuthNone)


@patch.dict(
    os.environ,
    {
        AUTH_METHOD_ENV: "api_key",
        AuthApiKey.AUTH_API_KEY_ENV: "a" * 32,
    },
    clear=True,
)
def test_get_auth_method_api_key():
    """
    Check that we select the expected authentication method - api_key
    """
    auth = get_auth()
    assert auth.method == AuthMethod.API_KEY
    assert isinstance(auth, AuthApiKey)
    assert auth._api_key == "a" * 32


@patch.dict(
    os.environ,
    {
        AUTH_METHOD_ENV: "none",
    },
    clear=True,
)
def test_auth_none():
    auth = get_auth()
    assert auth.method == AuthMethod.NONE
    # Check that we can provide no user secret or some random secret
    # # and still get positive authentication
    assert auth.authenticate()
    assert auth.authenticate("nonsense")


@patch.dict(
    os.environ,
    {
        AUTH_METHOD_ENV: "api_key",
        AuthApiKey.AUTH_API_KEY_ENV: "a" * 32,
    },
    clear=True,
)
def test_auth_api_key():
    auth = get_auth()
    assert auth.method == AuthMethod.API_KEY
    # Check if we can authenticate using expected key
    assert auth.authenticate("a" * 32)
    # Check that invalid key will fail
    assert not auth.authenticate("nononono")
    # Check that no or empty key will fail too
    assert not auth.authenticate()
    assert not auth.authenticate("")

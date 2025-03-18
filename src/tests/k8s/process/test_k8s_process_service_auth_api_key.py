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
Test(s) for k8s Process service authentication mechanisms
"""
import os

from unittest.mock import patch
from importlib import reload

from fastapi.testclient import TestClient

### Plumbing ###

# Disable OTEL and set env configuration before importing service code
env = {
    "TRACE_TO_CONSOLE": "false",
    "SERVICE_LOGGING_ENABLE_JSON": "false",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_TRACES_EXPORTER": "none",
    "K8S_PROCESS_SITE_NAME": "localhost",
    "K8S_PROCESS_USE_FAKE_REDIS": "true",
    "DFM_AUTH_METHOD": "api_key",
    "DFM_AUTH_API_KEY": "a" * 32,
}
for k, v in env.items():
    os.environ[k] = v

import k8s.process.process_fastapi  # noqa: E402

### Tests ###


def test_auth_api_key_no_header():
    """
    Check if we can hit all endpoints with authentication none
    """
    with patch.dict(os.environ, {"DFM_AUTH_METHOD": "api_key"}):
        # Force reinitialization of the app to update authentication method
        k8s.process.process_fastapi = reload(k8s.process.process_fastapi)
        with TestClient(k8s.process.process_fastapi.app) as test_client:
            app = k8s.process.process_fastapi.app
            for route in app.routes:
                print(f"Going to hit {route}")
                response = test_client.get(route.path)
                assert response.status_code == 403


def test_auth_api_key_good_header():
    """
    Check if we can hit all endpoints with authentication none
    """
    with patch.dict(os.environ, {"DFM_AUTH_METHOD": "api_key"}):
        # Force reinitialization of the app to update authentication method
        k8s.process.process_fastapi = reload(k8s.process.process_fastapi)
        with TestClient(k8s.process.process_fastapi.app) as test_client:
            app = k8s.process.process_fastapi.app
            for route in app.routes:
                response = test_client.get(route.path, headers={"X-DFM-Auth": "a" * 32})
                assert response.status_code != 403


def test_auth_api_key_wrong_header_value():
    """
    Check if we can hit all endpoints with authentication none
    """
    with patch.dict(os.environ, {"DFM_AUTH_METHOD": "api_key"}):
        # Force reinitialization of the app to update authentication method
        k8s.process.process_fastapi = reload(k8s.process.process_fastapi)
        with TestClient(k8s.process.process_fastapi.app) as test_client:
            app = k8s.process.process_fastapi.app
            for route in app.routes:
                response = test_client.get(route.path, headers={"X-DFM-Auth": "b" * 32})
                assert response.status_code == 403


def test_auth_api_key_wrong_header_name():
    """
    Check if we can hit all endpoints with authentication none
    """
    with patch.dict(os.environ, {"DFM_AUTH_METHOD": "api_key"}):
        # Force reinitialization of the app to update authentication method
        k8s.process.process_fastapi = reload(k8s.process.process_fastapi)
        with TestClient(k8s.process.process_fastapi.app) as test_client:
            app = k8s.process.process_fastapi.app
            for route in app.routes:
                # 'M' and 'F' are swapped in header name
                response = test_client.get(route.path, headers={"X-DMF-Auth": "a" * 32})
                assert response.status_code == 403

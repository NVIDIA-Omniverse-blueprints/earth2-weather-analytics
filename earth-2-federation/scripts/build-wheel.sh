#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# Build a wheel containing the federation module and publish to GitLab (and optionally URM).
# On main: use version from pyproject.toml, skip if that version tag already exists.
# On MR: use version 0.8.0.dev<MR_IID> so each MR gets a unique package.

set -ex

BUILD_WHEEL_OUTPUT_DIR=${BUILD_WHEEL_OUTPUT_DIR:-dist}

uv sync --all-extras --dev

# Generate the federation/fed/ directory
uv run dfm fed gen code --cleanup earth2

# Build the full wheel (contains the federation package per pyproject [tool.hatch.build.targets.wheel] packages = ["federation"])
uv -v build --wheel --out-dir="$BUILD_WHEEL_OUTPUT_DIR"

# Build the API-only wheel (federation.fed.api only, nv_dfm_core deps)
bash scripts/build-api-wheel.sh

echo "Wheels built in $BUILD_WHEEL_OUTPUT_DIR"
ls -la "$BUILD_WHEEL_OUTPUT_DIR"

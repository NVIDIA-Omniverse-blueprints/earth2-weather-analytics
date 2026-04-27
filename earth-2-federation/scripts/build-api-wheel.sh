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

# Build the API-only wheel (federation.api + federation.fed.api, minimal deps).
# Copies federation.api and federation.fed from repo into API package, then builds.
# Run from repo root. Output: dist/earth2_blueprint_api-*.whl

set -e

REPO_ROOT="${REPO_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$REPO_ROOT"

# Generation federation API code
uv run dfm fed gen code --cleanup --runtime-site homesite earth2

API_PKG="packages/earth2-blueprint-api"
FED="federation"

# Sync version from root pyproject (same as full package; root is already updated for MR in build-wheel.sh)
VERSION=$(sed -n 's/^version = "\(.*\)"$/\1/p' pyproject.toml)
if [[ -z "$VERSION" ]]; then
  echo "Could not read version from pyproject.toml"
  exit 1
fi
echo "Building API wheel version: $VERSION"

sed "s/^version = .*/version = \"$VERSION\"/" "$API_PKG/pyproject.toml" > "$API_PKG/pyproject.toml.tmp"
mv "$API_PKG/pyproject.toml.tmp" "$API_PKG/pyproject.toml"

BUILD_WHEEL_OUTPUT_DIR="${BUILD_WHEEL_OUTPUT_DIR:-dist}"
OUTDIR="$REPO_ROOT/$BUILD_WHEEL_OUTPUT_DIR"
mkdir -p "$OUTDIR"

# Copy federation.api and federation.fed from repo into API package (no checked-in federation tree).
rm -rf "$API_PKG/federation"
mkdir -p "$API_PKG/federation/api" "$API_PKG/federation/fed/api"
cp -r "$FED/fed" "$API_PKG/federation/"
# federation/__init__.py for API package (version from this package name)
cat > "$API_PKG/federation/__init__.py" << 'INIT'
# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

"""Earth-2 Blueprint Federation API (slim package)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("earth2-blueprint-api")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]
INIT

# Remove any existing API wheels so we verify the one we build (no stale from artifacts/cache)
rm -f "$OUTDIR"/earth2_blueprint_api-*.whl

# Build from an isolated copy so hatch's project root has no parent workspace (CI uv/hatch then include federation/).
# Wheel-only so we use on-disk source, not sdist.
API_BUILD_DIR=$(mktemp -d)
trap "rm -rf '$API_BUILD_DIR'" EXIT
cp -r "$API_PKG"/* "$API_BUILD_DIR/"
(cd "$API_BUILD_DIR" && uv -v build . --wheel --out-dir="$OUTDIR")

echo "API wheel built: $OUTDIR/earth2_blueprint_api-"*".whl"
ls -la "$OUTDIR"/earth2_blueprint_api-*.whl


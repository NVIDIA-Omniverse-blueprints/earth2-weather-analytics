# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary

"""Earth-2 Blueprint Federation API (slim package)."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("earth2-blueprint-api")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["__version__"]

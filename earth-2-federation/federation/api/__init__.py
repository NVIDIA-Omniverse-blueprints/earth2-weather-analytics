# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# Re-export API types from nv_dfm_lib_common.schemas (3.1.7+), fall back to nv_dfm_lib_weather.api for older envs.
try:
    from nv_dfm_lib_common.schemas import GeoJsonFile, TextureFile, TextureFileList
except (ModuleNotFoundError, ImportError):
    from nv_dfm_lib_weather.api import GeoJsonFile, TextureFile, TextureFileList

__all__ = [
    "TextureFile",
    "TextureFileList",
    "GeoJsonFile",
]

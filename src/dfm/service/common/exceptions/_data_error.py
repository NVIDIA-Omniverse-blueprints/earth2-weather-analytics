# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Raised when any external data is wrong, user-supplied or from other external sources.
E.g. unexpected xarray schema. Issues with internal data (e.g. from a dfm database) is
considered a CodeError"""
from ._dfm_error import DfmError


class DataError(DfmError):
    """Raised when any external data is wrong, user-supplied or from other external sources.
    E.g. unexpected xarray schema. Issues with internal data (e.g. from a dfm database) is
    considered a CodeError"""

    def __init__(self, message):
        super().__init__(message=message, http_status_code=400)

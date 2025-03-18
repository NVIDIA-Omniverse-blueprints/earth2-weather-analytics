# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Raised when anything goes wrong that is not directly due to illegal data"""
from ._dfm_error import DfmError


class ServerError(DfmError):
    """Raised when anything goes wrong that is not directly due to illegal data"""

    def __init__(self, message):
        super().__init__(message=message, http_status_code=500)

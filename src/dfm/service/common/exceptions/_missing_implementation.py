# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Raised when some feature is not (yet) implemented"""

from ._dfm_error import DfmError


class MissingImplementation(DfmError):
    """Raised when some feature is not (yet) implemented"""

    def __init__(self, message):
        super().__init__(message=message, http_status_code=501)

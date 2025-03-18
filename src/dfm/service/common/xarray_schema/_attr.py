# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""An xarray attribute that must exist on the dataset. Currently we only look for existance
and don't check attribute values. We also don't support attribute checking on dataarrays yet.
"""


class Attr:
    """An xarray attribute that must exist on the dataset. Currently we only look for existance
    and don't check attribute values. We also don't support attribute checking on dataarrays yet.
    """

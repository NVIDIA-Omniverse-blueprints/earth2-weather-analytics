# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""A marker class to annotate Dims or Vars that are indexed.
Use like Annotated[Var(...),Indexed]"""


class Indexed:
    """A marker class to annotate Dims or Vars that are indexed.
    Use like Annotated[Var(...),Indexed]"""

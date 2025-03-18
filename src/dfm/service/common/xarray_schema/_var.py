# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""A schema definition for a field that is a Variable"""
from typing import List, Optional, Tuple
import numpy as np


class Var:
    """A schema definition for a field that is a Variable"""

    dtype: np.dtype
    dims: List[str]
    minmax: Optional[Tuple[float, float]]

    def __init__(self, dtype, *dims, minmax=None):
        self.dtype = dtype
        self.dims = list(dims)
        self.minmax = minmax

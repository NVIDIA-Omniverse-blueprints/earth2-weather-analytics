# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Schema specification for a variable that's used as a dimension"""
from typing import Tuple, Optional
import numpy as np


class Dim:
    """Schema specification for a variable that's used as a dimension"""

    dtype: np.dtype
    size: int | Tuple[int | None, int] | Tuple[int, int | None]
    minmax: Optional[Tuple[float, float]]

    def __init__(self, dtype, size, minmax=None):
        self.dtype = dtype
        self.size = size
        self.minmax = minmax

    def some_valid_size(self) -> int:
        """Not sure this survives, but for now a helper function to return some
        size that is valid according to this Dim schema; used in XarraySchema.assemble_prototype
        """
        if isinstance(self.size, int):
            return self.size
        # I guess this could be generated more randomly, too
        return self.size[0] or self.size[1] or 1

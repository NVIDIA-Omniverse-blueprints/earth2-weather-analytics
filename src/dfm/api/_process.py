# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import datetime

from typing import Literal, Optional

from ..common import PolymorphicBaseModel
from ._block import Block
from .dfm import Execute


class Process(PolymorphicBaseModel, frozen=True):
    """
    A request to the DFM Process service for execution of a pipeline. The Process
    object can be used as a context manager to simplify the programatic construction
    of a pipeline.

    Args:
        site: The site where the pipeline should get executed.
        deadline: A deadline to delay execution. If the deadline is in the future, the
                Execute will be scheduled for later execution.
        execute: The Execute object containing the pipeline that should get executed.
    """

    api_class: Literal["dfm.api.Process"] = "dfm.api.Process"
    site: Optional[str] = None
    # Temporarily give the user a chance to delay execution
    deadline: Optional[datetime.datetime] = None
    # The script for the home site
    execute: Execute = Execute.model_validate(
        {"site": None}, context={"allow_outside_block": True}
    )

    def __enter__(self):
        Block._push_block(self.execute)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False
        Block._pop_block(self.execute)

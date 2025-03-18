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
from typing import Optional

from pydantic import UUID4, BaseModel
from dfm.api.dfm import Execute


class Job(BaseModel):
    """
    A Job is a request to execute a function.

    Fields:
        home_site: The site to execute the function on.
        request_id: The unique identifier for the job.
        deadline: The deadline for the job.
        is_discovery: Whether the job is a discovery job.
        execute: The function to execute.
    """

    home_site: str
    request_id: UUID4
    deadline: Optional[datetime.datetime] = None
    is_discovery: bool = False
    execute: Execute = Execute.model_validate(
        {"site": None}, context={"allow_outside_block": True}
    )

    def is_delayed(self):
        """
        Check if the job is delayed.

        Returns:
            True if the job is delayed, False otherwise.
        """
        return self.deadline is not None and self.deadline > datetime.datetime.now(
            datetime.UTC
        )

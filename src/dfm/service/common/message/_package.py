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
from functools import partial
from pydantic import BaseModel, Field
from ._job import Job


class Package(BaseModel):
    """
    A Package is a request to execute a function.

    Fields:
        timestamp: The timestamp when the package has been created.
        source_site: The site that created the package.
        target_site: The site that will execute the package.
        job: The job to execute.
    """

    # time when the package has been created. Uplink only tries to deliver packages
    # that aren't too old and gives up after a while
    timestamp: datetime.datetime = Field(
        default_factory=partial(datetime.datetime.now, datetime.timezone.utc)
    )
    source_site: str
    target_site: str
    job: Job

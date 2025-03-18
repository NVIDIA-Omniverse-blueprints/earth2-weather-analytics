# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from pydantic import BaseModel, UUID4


class ProcessResponse(BaseModel, frozen=True):
    """
    The ProcessResponse is returned by the Process service to inform
    the client about the generated request_id for a new execute request.
    The client can use this request_id to poll for responses.
    """

    request_id: UUID4

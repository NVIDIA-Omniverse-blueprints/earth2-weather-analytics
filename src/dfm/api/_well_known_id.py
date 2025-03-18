# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import hashlib
import uuid


def well_known_id(ident: int | str) -> uuid.UUID:
    """A helper function to construct a UUID from a string. This simplifies pipeline management
    because the UUIDs for a given FunctionCall node can be constructed anywhere from a string,
    instead of having to pass around the randomly generated UUID from the node."""
    if isinstance(ident, str):
        i = int(hashlib.sha256(ident.encode("utf-8")).hexdigest(), 16) % 10**8
    else:
        i = ident
    return uuid.UUID(int=i, version=4)

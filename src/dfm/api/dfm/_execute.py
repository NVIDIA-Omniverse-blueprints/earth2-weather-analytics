# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Literal, Optional

from .._block import Block
from .._function_call import FunctionCall


class Execute(FunctionCall, Block, frozen=True):
    """
    Function to encapsulate a block to be executed at the local or a remote
    site. When Execute executes, the block gets transferred via the Uplink
    services to the specified target sites and will get enqueued for execution
    until picked up by the site's Execute service. Executed blocks may issue
    subsequent calls to the Execute function to schedule new execute blocks.

    Args:
        site: The address of the target site that should execute this block.
        body: The inner block that gets scheduled on the given site.

    Function Returns:
        -

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.Execute"] = "dfm.api.dfm.Execute"

    site: Optional[str]

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

""""""

from typing import Literal
from .. import FunctionCall, Block


class AwaitMessage(FunctionCall, Block, frozen=True):
    """
    Function to await the arrival of a message in a named mailbox. Messages are
    sent pipelines through a SendMessage at the same or a remote site.

    Args:
        mailbox: String name of a virtual mailbox at the current site. The mailbox
                 is an arbitrary string but only messages sent to the same mailbox
                 will be received by this AwaitMessage function.
        sleeptime: A float defining the period between checks of the mailbox.
        wait_count: A counter specifying how often the AwaitMessage function has been
                    woken up already. Usually starts at 0 and automatically gets incremented.
                    The AwaitMessage block may get cancelled if the message doesn't arrive
                    until the counter reaches some provider-specific threshold.
        body: The inner block that gets scheduled once the message has arrived.

    Function Returns:
        AwaitMessage returns the value of the message to its inner block.

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.AwaitMessage"] = "dfm.api.dfm.AwaitMessage"
    mailbox: str
    sleeptime: float = 0.1
    wait_count: int = 0

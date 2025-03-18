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
from .. import FunctionCall, FunctionRef


class SendMessage(FunctionCall, frozen=True):
    """
    Function to send a string message to the local or a remote site. Messages
    get added to a mailbox at the target site. A mailbox is an arbitrary string
    that identifies the message queue at the target site. Messages are often used
    to orchestrate pipelines running on diffeent sites.

    Args:
        target_site: The address of the site that should receive the message.
        mailbox: An arbitrary string identifying the mailbox to which the message gets added.
        data: FunctionRef with the message to send. Can be a Constant or any other function
              that produces a meaningful string output (such as IDs or paths)

    Function Returns:
        -

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.SendMessage"] = "dfm.api.dfm.SendMessage"
    target_site: str
    mailbox: str
    data: FunctionRef

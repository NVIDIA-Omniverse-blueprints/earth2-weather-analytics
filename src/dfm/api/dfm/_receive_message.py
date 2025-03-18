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
from .. import FunctionCall


class ReceiveMessage(FunctionCall, frozen=True):
    """
    Function to place a new message in the mailbox at the target site.
    This function is not necessarily intended to be used directly by clients
    but is used internally by the DFM. The DFM may pack a message from the
    SendMessage function into a ReceiveMessage that gets sent to a remote
    site to add the message to the corresponding mailbox at the target site.

    Args:
        target_site: The site that receives the message in its mailbox.
        mailbox: An arbitrary string identifying the mailbox for the given message.
        messgae: The message.

    Function Returns:
        -

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.dfm.ReceiveMessage"] = "dfm.api.dfm.ReceiveMessage"
    target_site: str
    mailbox: str
    message: str

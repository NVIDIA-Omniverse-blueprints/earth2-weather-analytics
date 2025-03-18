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

from typing import Literal, List
from .. import FunctionCall, FunctionRef


class SignalAllDone(FunctionCall, frozen=True):
    """
    Function to send a simple string message to the client when the
    preceeding functions have completely finished. SignalAllDone is often used
    when it is unknown ahead of time how many responses a preceeding FunctionCall
    will produce. Clients can then wait for the specified message from the
    SignalAllDone to know when the preceeding functions have finished.

    Args:
        after: list of FunctionRefs of the functions after which the signal should be issued.
        message: String to send to the client when the signal is issued.
        is_output: Default set to True.

    Function Returns:
        String with the message.

    Client Returns:
        ValueResponse with the message string.
    """

    api_class: Literal["dfm.api.dfm.SignalAllDone"] = "dfm.api.dfm.SignalAllDone"
    after: List[FunctionRef]
    is_output: bool = True
    message: str = "Sig"

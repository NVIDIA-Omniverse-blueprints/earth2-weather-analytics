# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Function to invoke FourCastNet, a Numerical Weather Prediction (nwp) NIM."""

from typing import Literal

from .._adapter_config import AdapterConfig


class InvokeNimFourCastNet(AdapterConfig, frozen=True):
    """Config for FourCastNet Adapter"""

    adapter_class: Literal["adapter.nwp.InvokeNimFourCastNet"] = (
        "adapter.nwp.InvokeNimFourCastNet"
    )

    # seed: Seed being passed to the NIM.
    seed: int = 0
    # URL of the NIM instance.
    url: str
    # Timeout in seconds after which the connection to the NIM service gets closed.
    timeout: int = 600

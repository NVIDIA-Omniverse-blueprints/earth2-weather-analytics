# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""
Invoke a Numerical Weather Prediction (nwp) NIM.
"""

from typing import Dict, List, Literal, Optional
from .. import FunctionCall, FunctionRef


class InvokeNimNwpDnn(FunctionCall, frozen=True):
    """
    Function to invoke a Numerical Weather Prediction (nwp) NIM.

    Args:
        data: FunctionRef for the xarray containing the initial conditionas.
              The xarray is expected to have at least the
              variables required by the NIM.
        samples: Number of samples the NIM should produce as its output.
        variables: List of variables that should get returned from the NIM, or the wildcard
                   '*' for all available variables.
        selection: Selection passed to xarray.sel() on the xarray returned from the NIM.

    Function Returns:
        xarray, filtered by variables and selection if present

    Client Returns:
        -

    """

    api_class: Literal["dfm.api.nwp.InvokeNimNwpDnn"] = "dfm.api.nwp.InvokeNimNwpDnn"
    data: FunctionRef
    samples: int = 1
    variables: Literal["*"] | List[str]
    selection: Optional[Dict] = None

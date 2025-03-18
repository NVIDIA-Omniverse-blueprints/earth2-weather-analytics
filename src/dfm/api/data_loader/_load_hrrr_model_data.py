# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Earth2 Weather Analytics API to load HRRR Data"""

from typing import Literal, List

from .. import FunctionCall


class LoadHrrrModelData(FunctionCall, frozen=True):
    """
    Function to load HRRR data.

    Args:
        time: starting time of HRRR forecast
        step: step within simulation started at time (hour)
        variables: List of variables to return or the literal '*' to return all variables
                   the source provides.

    Function Returns:
        xarray.Dataset with the specified variables and selection.

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.data_loader.LoadHrrrModelData"] = (
        "dfm.api.data_loader.LoadHrrrModelData"
    )
    time: str
    step: int
    variables: Literal["*"] | List[str]

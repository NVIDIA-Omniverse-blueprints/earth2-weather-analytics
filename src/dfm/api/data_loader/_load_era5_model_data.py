# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Earth2 Weather Analytics API to load ERA5 Data"""

from typing import Literal, Dict, List, Optional

from .. import FunctionCall


class LoadEra5ModelData(FunctionCall, frozen=True):
    """
    Function to load NWP model data with the Era5 vocabulary. The source of the data
    depends on the configuration of the provider. If the source doesn't follow the ERA5
    nomenclature, the executing adapter will translate the variables to ERA5.

    Args:
        variables: List of era5 variables to return or the literal '*' to return all variables
                   the source provides.
        selection: Optional. A dictionary that is used for calling xarray.sel(**selection).

    Function Returns:
        xarray.Dataset with the specified variables and selection.

    Client Returns:
        -
    """

    api_class: Literal["dfm.api.data_loader.LoadEra5ModelData"] = (
        "dfm.api.data_loader.LoadEra5ModelData"
    )

    variables: Literal["*"] | List[str]
    selection: Optional[Dict] = None

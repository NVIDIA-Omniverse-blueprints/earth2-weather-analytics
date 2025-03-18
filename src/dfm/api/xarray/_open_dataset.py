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


class OpenDataset(FunctionCall, frozen=True):
    """
    Function to open an xarray.Dataset from a file in the storage location
    managed by the provider.

    Args:
        file: The filename of the xarray.Dataset to open.

    Function Returns:
        A xarray.Dataset

    Client Returns:
        -

    """

    api_class: Literal["dfm.api.xarray.OpenDataset"] = "dfm.api.xarray.OpenDataset"
    file: str

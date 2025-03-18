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


class WriteToZarr(FunctionCall, frozen=True):
    """
    Function to write an xarray.Dataset to a zarr file. The file will be
    stored in the storage configured in the provider.

    Args:
        dataset: FunctionRef for the xarray.Dataset.
        file: The filename to use.

    Function Returns:
        The provided filename from the args.

    Client Returns:
        A ValueResponse with the provided filename from the args.
    """

    api_class: Literal["dfm.api.xarray.WriteToZarr"] = "dfm.api.xarray.WriteToZarr"
    dataset: FunctionRef
    file: str

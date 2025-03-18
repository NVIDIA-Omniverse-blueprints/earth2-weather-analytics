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

from typing import Literal, Tuple, Union
from .. import FunctionCall, FunctionRef


class ConvertToUint8(FunctionCall, frozen=True):
    """
    Function to convert a 2+1 dimensional xarray.Dataset to uint8 in preparation
    of converting it to a grayscale image. If the dataset contains dimensions
    other than the time dimension and the x and y dimensions, those additional dimensions
    are summed up before conversion.
    Normalization takes the min and max arguments into account, if provided. Otherwise,
    the data will be normalized using the min and max present in the dataset.

    Args:
        data: FunctionRef for the xarray.Dataset to convert.
        time_dimension: The name of the time dimension.
        xydims: Tuple with the name of the x dimension and the y dimension respectively.
        min: Optional minimum used for normalization.
        max: Optional maximum used for normalization.
    """

    api_class: Literal["dfm.api.xarray.ConvertToUint8"] = (
        "dfm.api.xarray.ConvertToUint8"
    )
    data: FunctionRef
    time_dimension: str
    xydims: Tuple[str, str]
    min: Union[float, None] = None
    max: Union[float, None] = None

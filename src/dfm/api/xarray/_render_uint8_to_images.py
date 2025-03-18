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

from typing import Literal, Optional, Tuple, Any
from .. import FunctionCall, FunctionRef


class RenderUint8ToImages(FunctionCall, frozen=True):
    """
    Function to render a uint8 xarray.Dataset to an image. If the provider is configured
    to provide storage, the TextureFile will contain the URLs for the created image file and
    the metadata file. This data can alternatively be returned inline in the TextureFile
    response if return_image_data and/or return_meta_data is True.

    Args:
        data: FunctionRef for the xarray.Dataset
        time_dimension: The name of the time dimension.
        xydims: Tuple with the name of the x dimension and the y dimension respectively.
        variable: If the xarray.Dataset has more than one variable, selects which variable
                to render.
        return_image_data: If True, the image gets returned in the response as a base64
                encoded image.
        return_meta_data: If True, the metadata gets returned inlined in the response as a
                Dict.

    Function Returns:
        A TextureFile object.

    Client Returns:
        A ValueResponse with a TextureFile object in its body.
    """

    api_class: Literal["dfm.api.xarray.RenderUint8ToImages"] = (
        "dfm.api.xarray.RenderUint8ToImages"
    )
    data: FunctionRef
    time_dimension: str
    xydims: Tuple[str, str]
    # if data has more than one variable, which one should be rendered?
    variable: Optional[str] = None
    # if True, the response will directly contain the image data in base64_image_data
    return_image_data: bool = False
    # if True, the response will directly contain the metadata in metadata
    return_meta_data: bool = False
    # additional meta data to append to the output
    additional_meta_data: Optional[dict[str, Any]] = None

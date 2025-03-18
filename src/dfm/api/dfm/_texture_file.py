# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel


class TextureFile(BaseModel):
    """
    A response object containing information about a single texture file.
    For example, produced as the output of RenderUint8ToImages.
    The contents of TextureFile depends on the configuration of the provider and
    the parameters to the function producing the TextureFile response.
    A texture file may be returned as the URL of the storage location if the provider
    is configured to provide storage.
    And/or a texture file may be returned inline as a base64 encoded image if
    the clients indictates so in the function parameters.
    Similarly for metadata. Metadata may be returned as the URL of the storage location
    if metadata is present and the provider is configured to provide storage.
    And/or the metadata may be returned inline as a Dict if the client indicates
    so in the function parameters.

    Args:
        metadata_url: The URL of the metadata file, if a metadata file exists.
        url: The URL of the texture file, if a texture file exists.
        format: The format (jpeg, png, etc) of the texture file.
        timestamp: The timestamp of the texture, if the texture was associated with a time.
        base64_image_data: Base64 encoded inlined image, if requested.
        metadata: The inlined metadata dict, if requested.
    """

    api_class: Literal["dfm.api.dfm.TextureFile"] = "dfm.api.dfm.TextureFile"
    metadata_url: Optional[str] = None
    # if the dfm is configured to write the images, this will be the URL
    url: Optional[str]
    format: str
    timestamp: str
    base64_image_data: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

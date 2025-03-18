# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel


class TextureFilesBundle(BaseModel):
    """
    A response object returning a set of associated texture files. For example
    produced by ListTextureFiles.
    The provider may be configured to identify metadata files associated with a
    TextureFileBundle, in which case it can return the metadata url as well as,
    if the client requests it in the function parameters, the inlined contents
    of the metadata file as a dict.

    Args:
        metadata_url: The URL of the metadata file, if a metadata file exists.
        urls: A list of URLs of the texture files.
        metadata: The inlined metadata dict, if requested.
    """

    api_class: Literal["dfm.api.dfm.TextureFilesBundle"] = (
        "dfm.api.dfm.TextureFilesBundle"
    )
    metadata_url: Optional[str] = None
    # list of URLs to images
    urls: List[str]
    metadata: Optional[Dict[str, Any]] = None

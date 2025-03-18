# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Literal
from .. import FunctionCall


class ListTextureFiles(FunctionCall, frozen=True):
    """
    Function to list texture files with a given extension and a given base path
    inside a storage location configured by the provider. If configured by
    the provider and if present, the matching files under the given path may
    come with a metadata file.

    Args:
        path: The base path inside the storage location configured by the provider to
              list texture files in.
        format: The file extension of textures to return.
        return_meta_data: If True and the provider is configured for identifying metadata
                          and a metadata file is present, the metadata will be directly returned
                          as a Dict in the response.
        is_output: Default is set to True.

    Function Returns:
        A TextureFilesBundle with the list of files and optionally metadata found under the
        path in the provider's storage location.

    Client Returns:
        A ValueResponse with a TextureFilesBundle with the list of files and optionally
        metadata found under the path in the provider's storage location
    """

    api_class: Literal["dfm.api.dfm.ListTextureFiles"] = "dfm.api.dfm.ListTextureFiles"
    path: str
    format: Literal["png", "jpg", "jpeg"]
    # if True, the response will directly contain the metadata in metadata
    return_meta_data: bool = False
    # by default, ListTextureFiles will return its result to the client
    is_output: bool = True

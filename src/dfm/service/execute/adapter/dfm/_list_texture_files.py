# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import json
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import urlparse
from pathlib import PurePath

from pydantic import JsonValue
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.service.common.request import DfmRequest
from dfm.service.execute.discovery import field_advisor
from dfm.service.execute.discovery._advised_values import AdvisedOneOf
from dfm.service.execute.provider import FsspecProvider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.dfm import ListTextureFiles as ListTextureFilesParams, TextureFilesBundle
from dfm.config.adapter.dfm import ListTextureFiles as ListTextureFilesConfig


# joins paths that potentially start with a protocol
def join_url_paths(base_url: str, *paths: str) -> str:
    """
    Joins paths that potentially start with a protocol.
    """
    parsed_base_url = urlparse(base_url)
    base_path = parsed_base_url.path
    paths_only = [urlparse(p).path for p in paths]
    paths_only.insert(0, base_path)
    cleaned_path = PurePath(*paths_only).as_posix()

    ret_str = ""
    if parsed_base_url.scheme:
        ret_str += f"{parsed_base_url.scheme}://"
    if parsed_base_url.netloc:
        ret_str += parsed_base_url.netloc
    if ret_str and cleaned_path and not cleaned_path.startswith("/"):
        ret_str += f"/{cleaned_path}"
    else:
        ret_str += cleaned_path

    return ret_str


class ListTextureFiles(
    NullaryAdapter[FsspecProvider, ListTextureFilesConfig, ListTextureFilesParams]
):
    """
    A ListTextureFiles adapter is an adapter that lists texture files.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: FsspecProvider,
        config: ListTextureFilesConfig,
        params: ListTextureFilesParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    @field_advisor("path", order=1)
    async def advise_path(self, _value, _context):
        base_path = join_url_paths(
            self.provider.config.fsspec_conf.base_url, self.config.subfolder
        )
        fs = self.provider.get_filesystem()
        # we want to find values for the first two asterisks in this template
        filenames = fs.glob(f"{base_path}/*/*/*.{self.params.format}")
        paths = set()
        for filename in filenames:
            basename = os.path.basename(filename)
            pattern = f".*{base_path}/(.+)/{basename}"
            match = re.search(pattern, filename)
            if match and len(match.groups()) == 1:
                paths.add(match.groups()[0])
        return AdvisedOneOf(values=sorted(paths), split_on_advice=False)

    def body(self) -> Any:
        fs = self.provider.get_filesystem()

        path = join_url_paths(
            self.provider.config.fsspec_conf.base_url,
            self.config.subfolder,
            self.params.path,
        )

        # read metadata file, if present
        metadata_url: Optional[str] = None
        metadata_content: Optional[Dict[str, JsonValue]] = None
        if self.config.metadata_filename:
            try:
                metadata_file = join_url_paths(path, self.config.metadata_filename)
                if fs.exists(metadata_file) and self.params.return_meta_data:
                    metadata_url = (
                        join_url_paths(self.config.server_url, metadata_file)
                        if self.config.server_url
                        else metadata_file
                    )
                    with fs.open(metadata_file, mode="r") as filename:
                        metadata_content = json.loads(filename.read())
            except Exception as e:  # pylint: disable=broad-exception-caught
                self._logger.info("Could not read metadata file %s", metadata_file)
                self._logger.exception(e)
                # we keep going, returning None

        # Find files
        urls = []
        filenames = fs.glob(f"{path}/*.{self.params.format}")
        assert isinstance(filenames, list)
        for filename in filenames:
            basename = os.path.basename(str(filename))
            base_url = join_url_paths(path, basename)
            url = (
                join_url_paths(self.config.server_url, base_url)
                if self.config.server_url
                else base_url
            )
            urls.append(url)

        response = TextureFilesBundle(
            metadata_url=metadata_url, metadata=metadata_content, urls=urls
        )
        return response

    async def prepare_to_send(
        self, result: TextureFilesBundle
    ) -> ResponseBody:  # pylint: disable=arguments-renamed
        return ValueResponse(value=result.model_dump())

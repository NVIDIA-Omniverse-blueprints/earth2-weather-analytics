# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any
import xarray
from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import FsspecProvider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.config.adapter.xarray import OpenDataset as OpenDatasetConfig
from dfm.api.xarray import OpenDataset as OpenDatasetParams

from dfm.service.execute.discovery import field_advisor, AdvisedOneOf


class OpenDataset(NullaryAdapter[FsspecProvider, OpenDatasetConfig, OpenDatasetParams]):
    """
    An OpenDataset adapter is an adapter that opens a dataset.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: FsspecProvider,
        config: OpenDatasetConfig,
        params: OpenDatasetParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    @field_advisor("file", order=0)
    async def available_files(self, _value, _context):
        fs = self.provider.get_filesystem(asynchronous=True)
        full_url = self.provider.full_url(
            self.config.base_url, f"/**/*.{self.config.filetype}"
        )
        files = fs.glob(full_url)
        return AdvisedOneOf(values=files)

    def body(self) -> Any:
        if not self.params.file.endswith(self.config.filetype):
            raise DataError(
                f"{self.provider.provider}.OpenDataset only provides"
                f" files of type {self.config.filetype}"
            )

        full_url = self.provider.full_url(self.config.base_url, self.params.file)
        backend_kwargs = {"storage_options": self.provider.storage_options}
        engine = self.config.filetype
        ds = xarray.open_dataset(full_url, backend_kwargs=backend_kwargs, engine=engine)
        return ds

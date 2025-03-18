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
from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.execute.provider import FsspecProvider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.config.adapter.xarray import WriteToZarr as WriteToZarrConfig
from dfm.api.xarray import WriteToZarr as WriteToZarrParams


class WriteToZarr(
    UnaryAdapter[FsspecProvider, WriteToZarrConfig, WriteToZarrParams],
    input_name="dataset",
):
    """
    A WriteToZarr adapter is an adapter that writes a dataset to a Zarr store.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: FsspecProvider,
        config: WriteToZarrConfig,
        params: WriteToZarrParams,
        dataset: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, dataset)

    def body(self, dataset) -> Any:
        if not self.params.file.endswith(".zarr"):
            raise DataError(
                f"{self.provider.provider}.WriteToZarr only allows"
                " filenames with ending '.zarr'"
            )

        fs = self.provider.get_filesystem()
        url = self.provider.full_url(self.config.base_url, self.params.file)
        if fs.exists(url):
            fs.rm(url, recursive=True)
        fsmapper = self.provider.get_mapper(url)
        dataset.to_zarr(store=fsmapper)
        return self.params.file

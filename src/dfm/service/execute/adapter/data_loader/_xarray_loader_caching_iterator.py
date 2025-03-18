# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, List
import xarray
from dfm.config.common._fsspec_conf import FsspecConf
from dfm.service.common.exceptions import ServerError
from dfm.service.execute.adapter._adapter import Adapter
from dfm.service.execute.adapter._caching_iterator import CachingIterator


class XarrayLoaderCachingIterator(CachingIterator):
    """
    A XarrayLoaderCachingIterator is a caching iterator for the XarrayLoader adapter.
    It is used to cache the xarray datasets in the cache folder.
    """

    def __init__(
        self, adapter: Adapter, cache_info: FsspecConf, file_prefix: str = "dataset"
    ):
        if cache_info.protocol != "file":
            raise ServerError(
                f"Currently, xarray caching only supports local files, not {cache_info.protocol}"
            )
        super().__init__(adapter, cache_info)
        self._file_prefix = file_prefix

    async def write_value_to_cache(self, element_counter: int, item: Any):
        file = f"{self.full_cache_folder_path}/{self._file_prefix}_{element_counter}.nc"
        item.to_netcdf(file, "w")
        self._logger.info(
            "Caching xarray dataset number %s to %s",
            element_counter,
            self.full_cache_folder_path,
        )

    async def load_values_from_cache(
        self, expected_num_elements: int
    ) -> List[Any] | None:
        results: List[xarray.Dataset] = []
        for i in range(expected_num_elements):
            filename = f"{self.full_cache_folder_path}/{self._file_prefix}_{i}.nc"
            ds = xarray.open_dataset(filename, chunks={})
            results.append(ds)
        self._logger.info(
            "Loaded %s CACHED xarray dataset(s) from %s",
            expected_num_elements,
            self.full_cache_folder_path,
        )
        return results

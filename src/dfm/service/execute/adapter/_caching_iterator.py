# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from abc import abstractmethod
import asyncio
from datetime import datetime
import hashlib
from typing import Any, ClassVar, Dict, List, Optional, Tuple
import fsspec
from pydantic import BaseModel, Field

from dfm.service.common.logging import getLogger
from dfm.service.common.logging._logging import shorten

from ._adapter import Adapter
from ._stream import Stream
from ....service.common.exceptions import ServerError
from ....config.common import FsspecConf


class CacheMetadata(BaseModel):
    """Object we use to get Pydantic json serialization"""

    FILENAME: ClassVar[str] = "_dfm_cache_metadata.json"
    created: datetime = Field(default_factory=datetime.now)
    hash_dict: Dict[str, Any]


class CacheSentinel(BaseModel):
    """Object we write to a folder to indicate that all values of a stream have
    been written to the cache"""

    FILENAME: ClassVar[str] = "_dfm_cache_sentinel.json"
    created: datetime = Field(default_factory=datetime.now)
    num_elements_written: int


class CachingIterator:
    """
    A CachingIterator is a caching iterator for an adapter.
    It is used to cache the output of an adapter in the cache folder.
    """

    def __init__(self, adapter: Adapter, cache_info: FsspecConf):
        self._adapter = adapter
        self._memoized_hash: Optional[Tuple[str, Dict[str, Any]]] = None
        self._cache_info = cache_info
        self._cache_folder_name = self.cache_folder_name()
        self._full_cache_folder_path: str = (
            f"{self._cache_info.base_url}/{self._cache_folder_name}"
        )
        self._filesystem: Any = fsspec.filesystem(
            self._cache_info.protocol, **self._cache_info.storage_options
        )
        self._task: Optional[asyncio.Task] = None

        self._logger = getLogger(
            f"{self.__class__.__name__} CachingIterator for"
            f" adapter {self._adapter.__class__.__name__}",
            self._adapter.dfm_request,
        )

    # =================================
    # Computing a hash key for the cache
    # =================================
    def _collect_hash_dict_for_adapter(self, adapter: Adapter) -> Dict[str, Any]:
        """Traverse the adapter and its input adapters to assemble a dictionary of
        all information that goes into calculating the hash to be used as a key for caching.
        Usually, this contains all the adapter parameters (with a few exceptions that
        are not influencing the produced values) and recursively the input adapter's parameters.
        If more complex logic is needed (e.g. if some adapters should be ignored or partially
        ignored when computing the hash) then this method can be overridden.
        """
        # start with everything the adapter deems important
        hash_dict: Dict[str, Any] = adapter.collect_local_hash_dict()

        # now traverse upwards and add all the inputs
        for name in adapter.get_adapter_input_names():
            if adapter.get_input_kind(name) == "adapter_list":
                input_dicts = []
                for input_adapter in adapter.get_input_adapter_list(name):
                    input_dicts.append(
                        self._collect_hash_dict_for_adapter(input_adapter)
                    )
                hash_dict[name] = input_dicts
            else:
                hash_dict[name] = self._collect_hash_dict_for_adapter(
                    adapter.get_input_adapter(name)
                )
        return hash_dict

    def pipeline_hash_key(self) -> str:
        """Collects the hash dict representing the pipeline up to self._adapter and translates
        this into a hash that can be used as a key for caching."""
        if self._memoized_hash is None:
            hash_dict = self._collect_hash_dict_for_adapter(self._adapter)
            hash_key = hashlib.sha256(str(hash_dict).encode("utf-8")).hexdigest()
            self._memoized_hash = (hash_key, hash_dict)
        return self._memoized_hash[0]

    def cache_folder_name(self) -> str:
        """Override this to support different naming scheme"""
        return f"dfm_cache_{self.pipeline_hash_key()}"

    @property
    def full_cache_folder_path(self) -> str:
        return self._full_cache_folder_path

    @property
    def filesystem(self) -> Any:
        return self._filesystem

    @property
    def adapter(self) -> Adapter:
        return self._adapter

    # =================================
    # loading from existing cache
    # =================================
    @abstractmethod
    async def load_values_from_cache(
        self, expected_num_elements: int
    ) -> List[Any] | None:
        """Override this method to load the actual data from the cache folder"""

    def expected_num_cache_elements(self) -> int:
        """Check if the sentinel file exists and return the number of expected
        cache elements stored in the sentinel file.
        0 if cache isn't good (eg folder or sentinel file don't exist or cannot
        be opened)"""
        filepath = f"{self._full_cache_folder_path}/{CacheSentinel.FILENAME}"
        self._logger.info(
            "Checking if cache folder and sentinel file exist: %s", filepath
        )
        try:
            if not self._filesystem.exists(filepath):
                self._logger.info(
                    "Cache folder or sentinel file does NOT exist: %s", filepath
                )
                return 0

            sentinel = self.read_cache_sentinel()
            return sentinel.num_elements_written
        except Exception as ex:  # pylint: disable=broad-exception-caught
            self._logger.error(
                "Error while checking if cache folder and sentinel file exist: %s",
                filepath,
            )
            self._logger.exception(ex)
            return 0

    async def try_creating_stream_from_cache(self) -> Stream | None:
        try:
            expected_num_elements = self.expected_num_cache_elements()
            if expected_num_elements == 0:
                return None

            self._logger.info(
                "%s Cache appears to be complete, trying to load data from cache: %s",
                self,
                self._full_cache_folder_path,
            )
            values = await self.load_values_from_cache(
                expected_num_elements
            )  # pylint: disable=assignment-from-none
            if not values:
                self._logger.info("Didn't get values from cache, returning None")
                return None
            self._logger.info("Loaded %s values from cache", len(values))
            # wrap the values in Future objects
            loop = asyncio.get_event_loop()
            futures = []
            for v in values:
                future = loop.create_future()
                future.set_result(v)
                futures.append(future)
            return Stream.from_futures_in_order(
                self.adapter.__class__.__name__,
                self.adapter.dfm_request.request_id,
                self._adapter.params.node_id,
                futures,
            )
        except Exception as ex:  # pylint: disable=broad-exception-caught
            self._logger.info(
                "%s Could not create stream from cache path %s. Error: %s",
                self,
                self._full_cache_folder_path,
                ex,
            )
            return None

    # =================================
    # Preparing the cache folder
    # =================================
    async def _clear_and_prepare_cache_folder(self):
        assert self._filesystem
        assert self._full_cache_folder_path

        try:
            if self._filesystem.exists(self._full_cache_folder_path):
                self._logger.info(
                    "Trying to delete existing cache: %s", self._full_cache_folder_path
                )
                self._filesystem.rm(self._full_cache_folder_path, recursive=True)
                self._logger.info(
                    "Successfully deleted existing cache: %s",
                    self._full_cache_folder_path,
                )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error(
                "Failed to delete existing cache: %s", self._full_cache_folder_path
            )
            self._logger.exception(e)

        # create the cache
        self._logger.info(
            "Creating new cache directory: %s", self._full_cache_folder_path
        )
        try:
            self._filesystem.mkdir(self._full_cache_folder_path)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.info(
                "Could not create cache directory: %s", self._full_cache_folder_path
            )
            self._logger.exception(e)

    # =================================
    # Writing various files and data to the cache
    # =================================
    async def _write_cache_metadata(self):
        if not self._full_cache_folder_path or not self._filesystem:
            raise ServerError("Cache needs to be opened before trying to write to it")

        filepath = f"{self._full_cache_folder_path}/{CacheMetadata.FILENAME}"
        # delete, if exists
        try:
            if self._filesystem.exists(filepath):
                self._logger.info("Deleting existing cache metadata file: %s", filepath)
                self._filesystem.rm(self._full_cache_folder_path, recursive=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error("Failed to delete existing cache metadata: %s", filepath)
            self._logger.exception(e)
        # and write
        try:
            self._logger.info("Writing cache metatata file: %s", filepath)
            metadata_info = CacheMetadata(
                hash_dict=(
                    self._memoized_hash[1]
                    if self._memoized_hash
                    else {
                        "unknown": f"self._memoized_hash was none in CachingIterator {self.__class__.__name__}"
                    }
                )
            )
            self._filesystem.pipe(
                filepath, metadata_info.model_dump_json(indent=4).encode("utf-8")
            )
            self._logger.info("Done writing cache metadata file: %s", filepath)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.info("Could not write cache metadata file %s", filepath)
            self._logger.exception(e)

    async def _write_cache_sentinel(self, num_elements_written: int):
        if not self._full_cache_folder_path or not self._filesystem:
            raise ServerError("Cache needs to be opened before trying to write to it")

        filepath = f"{self._full_cache_folder_path}/{CacheSentinel.FILENAME}"
        # delete, if exists
        try:
            if self._filesystem.exists(filepath):
                self._logger.info(
                    "%s Deleting existing cache sentinel file: %s", self, filepath
                )
                self._filesystem.rm(filepath, recursive=False)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.error(
                "%s Failed to delete existing cache sentinel: %s", self, filepath
            )
            self._logger.exception(e)
        # and write
        try:
            self._logger.info("%s Writing cache sentinel file: %s", self, filepath)
            metadata_info = CacheSentinel(num_elements_written=num_elements_written)
            self._filesystem.pipe(
                filepath, metadata_info.model_dump_json(indent=4).encode("utf-8")
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.info("Could not write cache sentinel file %s", filepath)
            self._logger.exception(e)

    def read_cache_sentinel(self) -> CacheSentinel:
        fs = self.filesystem
        filepath = f"{self._full_cache_folder_path}/{CacheSentinel.FILENAME}"
        try:
            if not fs.exists(filepath):
                raise ServerError("Sentinel file not found")
            with fs.open(filepath, mode="r") as f:
                sentinel = CacheSentinel.model_validate_json(f.read())
            return sentinel
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.info("Could not read cache sentinel file %s", filepath)
            self._logger.exception(e)
            raise ServerError("Sentinel file not found") from e

    @abstractmethod
    async def write_value_to_cache(self, element_counter: int, item: Any):
        """The CachingIterator's run() method calls this method for
        each value returned by the adapter's stream.
        If this is the value, that should be written to the cache, then do this here.
        If the adapter wants finer control over what is cached (e.g. adapter
        returns a filename, but it's not the filename that should get cached but
        the contents of the file) then the adapter should call some custom method
        in this CachingIterator to write the file (e.g. write_contents(self, filename, result)).
        Leave this method empty in this case. The CachingIterator should still poll the stream
        results and call this empty method, to make sure that the whole stream gets produced
        so that the sentinel file can be written.
        Returns filename of the file written"""

    # =================================
    # The async task that iterates
    # the adapter stream
    # =================================
    def start_caching_task(self):
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._run())

    def cancel(self):
        if self._task:
            self._task.cancel()

    @property
    def task(self) -> asyncio.Task | None:
        return self._task

    async def _run(self):
        if not hasattr(self._adapter, "_stream"):
            # the caching iterator is started by the adapter as soon as the adapter's stream
            # is created. This happens inside get_or_create_stream(). This has the danger of
            # causing an infinite loop if the ordering is wrong, because we call
            # adapter.get_or_create_stream() below.
            raise ServerError(
                "Don't try to run the caching iterator before adapter's stream exists"
            )
        try:
            self._logger.info(
                "CachingIterator task is running. Clearing and preparing the cache folder"
            )
            await self._clear_and_prepare_cache_folder()
            self._logger.info("Writing the metadata file")
            await self._write_cache_metadata()
            num_elements = 0
            # poll results from the stream until the stream gets closed
            async for item in await self._adapter.get_or_create_stream():
                self._logger.info(
                    "Adapter produced a value, writing it to cache %s: %s",
                    self._full_cache_folder_path,
                    shorten(str(item)),
                )
                await self.write_value_to_cache(num_elements, item)
                num_elements += 1
            # stream ended normally
            self._logger.info("Writing the sentinel")
            await self._write_cache_sentinel(num_elements_written=num_elements)
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.info("Error while running caching iterator")
            self._logger.exception(e)

        self._logger.info("Shutting down")

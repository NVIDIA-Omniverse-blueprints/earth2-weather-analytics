# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import os
from typing import Any, List
import pytest
from dfm.api import FunctionCall
from dfm.api.dfm import GreetMe as GreetMeParams
from dfm.config.adapter.dfm import GreetMe as GreetMeConfig
from dfm.config.common._fsspec_conf import FsspecConf
from dfm.service.execute.adapter._caching_iterator import CachingIterator
from dfm.service.execute.adapter.dfm import GreetMe

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


@pytest.mark.asyncio
async def test_successfully_cache_multiple_values():
    FunctionCall.set_allow_outside_block()
    config = GreetMeConfig(greeting="Hello")
    params = GreetMeParams(name="World")

    cache_info = FsspecConf(protocol="file", base_url="tests/files/testoutputs/caching")

    class GreetMeCacher(CachingIterator):
        async def load_values_from_cache(
            self, _expected_num_elements: int
        ) -> List[Any] | None:
            return None

        async def write_value_to_cache(self, element_counter: int, item: str):
            filepath = f"{self._full_cache_folder_path}/file_{element_counter}.txt"
            self._filesystem.pipe(filepath, item.encode("utf-8"))

    class CachingGreetMe(GreetMe):
        def _instantiate_caching_iterator(self):
            return GreetMeCacher(self, cache_info)

        def body(self) -> Any:
            async def async_body():
                for i in range(3):
                    result = f"{self.config.greeting} {self.params.name} nr {i}"
                    yield result

            return async_body()

    adapter = CachingGreetMe(
        MockDfmRequest(this_site="here"),
        None,  # provider # type: ignore
        config,
        params,
    )
    FunctionCall.unset_allow_outside_block()

    assert adapter.caching_iterator is None
    stream = await adapter.get_or_create_stream()
    # creating the stream should create the cacher
    assert adapter.caching_iterator
    cache_it: GreetMeCacher = adapter.caching_iterator
    assert cache_it.task
    # hardcoding to make sure hash keys are stable
    assert (
        cache_it.pipeline_hash_key()
        == "6c90613e791e954f0178a5edc9107b3c86768670f449f73b5bb2f8a1ee66a358"
    )

    async for value in stream:
        print(value)

    await cache_it.task
    assert cache_it.expected_num_cache_elements() > 0
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/_dfm_cache_metadata.json")
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/_dfm_cache_sentinel.json")
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/file_0.txt")
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/file_1.txt")
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/file_2.txt")


@pytest.mark.asyncio
async def test_exception_must_result_in_incomplete_cache():
    FunctionCall.set_allow_outside_block()
    config = GreetMeConfig(greeting="Hello")
    params = GreetMeParams(name="World")

    cache_info = FsspecConf(protocol="file", base_url="tests/files/testoutputs/caching")

    class GreetMeCacher(CachingIterator):
        async def load_values_from_cache(
            self, _expected_num_elements: int
        ) -> List[Any] | None:
            return None

        async def write_value_to_cache(self, element_counter: int, item: str):
            filepath = f"{self._full_cache_folder_path}/file_{element_counter}.txt"
            self._filesystem.pipe(filepath, item.encode("utf-8"))

    class CachingGreetMe(GreetMe):
        def _instantiate_caching_iterator(self):
            return GreetMeCacher(self, cache_info)

        def body(self) -> Any:
            async def async_body():
                for i in range(3):
                    result = f"{self.config.greeting} {self.params.name} nr {i}"
                    if i == 2:
                        raise ValueError("Testing exception when stuff went wrong")
                    yield result

            return async_body()

    adapter = CachingGreetMe(
        MockDfmRequest(this_site="here"),
        None,  # provider # type: ignore
        config,
        params,
    )
    FunctionCall.unset_allow_outside_block()

    assert adapter.caching_iterator is None
    stream = await adapter.get_or_create_stream()
    # creating the stream should create the cacher
    assert adapter.caching_iterator
    cache_it: GreetMeCacher = adapter.caching_iterator
    assert cache_it.task
    # hardcoding to make sure hash keys are stable
    assert (
        cache_it.pipeline_hash_key()
        == "6c90613e791e954f0178a5edc9107b3c86768670f449f73b5bb2f8a1ee66a358"
    )

    with pytest.raises(ValueError):
        async for value in stream:
            print(value)

    await cache_it.task
    assert cache_it.expected_num_cache_elements() == 0
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/_dfm_cache_metadata.json")
    assert not os.path.isfile(
        f"{cache_it.full_cache_folder_path}/_dfm_cache_sentinel.json"
    )
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/file_0.txt")
    assert os.path.isfile(f"{cache_it.full_cache_folder_path}/file_1.txt")
    assert not os.path.isfile(f"{cache_it.full_cache_folder_path}/file_2.txt")

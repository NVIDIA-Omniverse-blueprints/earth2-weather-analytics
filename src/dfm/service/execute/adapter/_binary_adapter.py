# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator
from dfm.service.common.exceptions import MissingImplementation
from dfm.service.common.request import DfmRequest

from ._adapter import Adapter, ProviderT, ConfT, FunCallT
from ._body_results import BodyResultT, body_result_to_async_generator


class BinaryZipAdapter(Adapter[ProviderT, ConfT, FunCallT], ABC):
    """
    A BinaryZipAdapter is an adapter that takes two inputs and returns a single output.
    """

    @classmethod
    def __init_subclass__(cls, /, input1_name: str, input2_name: str, **kwargs):
        cls._input1_name = input1_name
        cls._input2_name = input2_name

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: ProviderT,
        config: ConfT,
        params: FunCallT,
        _1: Adapter,
        _2: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params)
        self._set_input_adapter(self._input1_name, _1)
        self._set_input_adapter(self._input2_name, _2)

    async def stream_body(self) -> AsyncIterator[Any]:
        """
        A stream_body is a function that streams the body of the adapter.
        """
        input1 = self.get_input_adapter(self._input1_name)
        input2 = self.get_input_adapter(self._input2_name)
        try:
            iter_1 = aiter(await input1.get_or_create_stream())  # noqa: F821
            iter_2 = aiter(await input2.get_or_create_stream())  # noqa: F821
            while True:
                # Check if input is still healthy
                iter_1.raise_if_exception()
                iter_2.raise_if_exception()
                # one will throw a StopAsyncIteration exception when the stream is empty,
                # which is when we stop
                input_1 = await anext(iter_1)  # noqa: F821
                input_2 = await anext(iter_2)  # noqa: F821
                # Note: don't await the body here
                result = self.body(
                    **{self._input1_name: input_1, self._input2_name: input_2}
                )
                async for res in body_result_to_async_generator(result):
                    yield res
        except StopAsyncIteration:
            pass

    @abstractmethod
    def body(self, _1: Any, _2: Any) -> BodyResultT:
        raise MissingImplementation(f"Body of adapter {self} not implemented")

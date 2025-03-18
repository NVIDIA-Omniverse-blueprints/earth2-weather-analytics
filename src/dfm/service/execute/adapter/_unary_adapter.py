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


class UnaryAdapter(Adapter[ProviderT, ConfT, FunCallT], ABC):
    """
    A UnaryAdapter is an adapter that takes a single input and returns a single output.
    """

    @classmethod
    def __init_subclass__(cls, /, input_name: str, **kwargs):
        cls._input_name = input_name

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: ProviderT,
        config: ConfT,
        params: FunCallT,
        _1: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params)
        self._set_input_adapter(self._input_name, _1)

    async def stream_body(self) -> AsyncIterator[Any]:
        input_adapter = self.get_input_adapter(self._input_name)
        input_stream = await input_adapter.get_or_create_stream()
        async for item in input_stream:
            # Check if input is still healthy
            input_stream.raise_if_exception()
            # Note: don't await the body here
            result = self.body(**{self._input_name: item})
            async for res in body_result_to_async_generator(result):
                yield res

    @abstractmethod
    def body(self, _: Any) -> BodyResultT:
        raise MissingImplementation(f"Body of adapter {self} not implemented")

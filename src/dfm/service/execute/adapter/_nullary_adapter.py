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
from ._adapter import Adapter, ProviderT, ConfT, FunCallT
from ._body_results import BodyResultT, body_result_to_async_generator


class NullaryAdapter(Adapter[ProviderT, ConfT, FunCallT], ABC):
    """
    A NullaryAdapter is an adapter that takes no input and returns a single output.
    """

    async def stream_body(self) -> AsyncIterator[Any]:
        # Note: don't await the body here
        result = self.body()
        async for res in body_result_to_async_generator(result):
            yield res

    @abstractmethod
    def body(self) -> BodyResultT:
        raise MissingImplementation(f"Body of adapter {self} not implemented")

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import uuid


class MockStreamIterator:
    def __init__(self, stream):
        self._stream = stream
        self._counter = 0

    async def __anext__(self):
        if self._counter >= len(self._stream._values):
            raise StopAsyncIteration()
        value = self._stream._values[self._counter]
        self._counter += 1
        return value

    def raise_if_exception(self):
        self._stream.raise_if_exception()


class MockStream:
    def __init__(self, values):
        self._values = values

    def __aiter__(self):
        return MockStreamIterator(self)

    def raise_if_exception(self):
        pass


class MockAdapter:
    def __init__(self, values):
        self._values = values
        self.node_id = uuid.uuid4()

    async def get_or_create_stream(self):
        return MockStream(self._values)

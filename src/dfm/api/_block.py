# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Dict
from pydantic import UUID4, BaseModel

from ._function_call import FunctionCall


class Block(BaseModel, frozen=True):
    """
    A Block is a FunctionCall that contains a pipeline as its body.
    A FunctionCall that is defined as a block usually will wait for some condition
    to become true and then issue its body for execution.
    Blocks are effectively implementing a Continuation Passing Style execution model.

    Args:
        body: The body of the block as a dict of {node_id: FunctionCall} pairs.
    """

    body: Dict[UUID4, FunctionCall] = {}

    def add_to_body(self, func: FunctionCall):
        self.body[func.node_id] = func

    def __enter__(self):
        Block._push_block(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            return False
        Block._pop_block(self)

    @classmethod
    def _push_block(cls, block: "Block"):
        # we don't want to declare _block_stat in the class because Pydantic will
        # add it to the model. So we create it lazily
        if not hasattr(Block, "_block_stack"):
            Block._block_stack = []
        Block._block_stack.append(block)

    @classmethod
    def _pop_block(cls, block: "Block"):
        if not hasattr(Block, "_block_stack") or not Block._block_stack:
            raise RuntimeError("Tried to pop block from empty stack")
        if Block._block_stack[-1] != block:
            raise RuntimeError(
                "Illegal pop from block stack: popping block that was not on top"
            )
        Block._block_stack.pop()
        if len(Block._block_stack) == 0:
            # not necessary, but we are cleaning up after ourselves
            delattr(Block, "_block_stack")

    @classmethod
    def get_block(cls) -> "Block":
        """Get the current block from the block stack.

        Returns:
            Block: The block at the top of the stack.

        Raises:
            RuntimeError: If there is no block context (empty stack).
        """
        if not hasattr(Block, "_block_stack") or not Block._block_stack:
            raise RuntimeError("No surrounding Process or block context found.")
        return Block._block_stack[-1]

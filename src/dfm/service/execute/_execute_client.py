#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


"""
Implementation of Execute service client
"""

import abc
import os

from dfm.service.execute import Execute


class ExecuteClient(abc.ABC):
    """
    Class is a local representation of an Execute service
    """

    @abc.abstractmethod
    def get_random_int(self, max_value: int):
        """
        This has to be implemented by the inheriting class.
        It should return a random integer between 0 and max_value.
        """
        pass


class ExecuteClientLocal(ExecuteClient):
    """
    Client implementation for local calls
    """

    def __init__(self) -> None:
        self.execute = Execute()

    def get_random_int(self, max_value: int):
        """
        A get_random_int is a function that returns a random integer.
        """
        return self.execute.get_random_int(max_value)


def get_client() -> ExecuteClient:
    """
    A get_client is a function that returns the execute client.
    """
    e = os.environ.get("EXECUTE_CLIENT", "local")
    if e == "local":
        return ExecuteClientLocal()
    elif e == "rest":
        from k8s.execute import ExecuteClientFastApi

        return ExecuteClientFastApi()
    else:
        raise RuntimeError(f"Unknown execute client {e}")

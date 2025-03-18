# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict, List, Literal
from dfm.service.common.request import DfmRequest
from dfm.api import FunctionCall
from dfm.config import AdapterConfig
from dfm.service.execute.adapter import Adapter


class UninitializedAdapter:
    """
    An uninitialized adapter is an adapter that is not yet initialized.
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        adapter_instance: Adapter,
        provider: Any,
        config: AdapterConfig | None,
        params: FunctionCall,
    ):
        """
        Initialize the UninitializedAdapter.
        """
        self._dfm_request = dfm_request
        self._adapter_instance = adapter_instance
        self._provider = provider
        self._config = config
        self._params = params

    @property
    def adapter_instance(self) -> Adapter:
        return self._adapter_instance

    @property
    def params(self) -> FunctionCall:
        return self._params

    def finish_init(
        self, input_adapters: Dict[str, Adapter | List[Adapter]]
    ) -> Adapter:
        self._adapter_instance.__init__(  # pylint: disable=unnecessary-dunder-call
            self._dfm_request,
            self._provider,
            self._config,
            self._params,
            **input_adapters
        )
        return self._adapter_instance

    def get_adapter_input_names(self) -> List[str]:
        """
        Get the input names for the adapter.
        """
        return self._adapter_instance.get_adapter_input_names()

    def get_input_kind(self, name: str) -> Literal["adapter", "adapter_list"] | None:
        """
        Get the input kind for the adapter.
        """
        return self._adapter_instance.get_input_kind(name)

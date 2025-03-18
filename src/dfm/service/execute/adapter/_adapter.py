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
import inspect
import textwrap
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Generic,
    List,
    Literal,
    Optional,
    Set,
    TypeVar,
)
from typing import get_args

from pydantic import BaseModel

from dfm.api import FunctionCall
from dfm.service.common.exceptions import ServerError
from dfm.service.common.request import DfmRequest
from dfm.api.response import ResponseBody, ValueResponse
from dfm.config.adapter import AdapterConfig

from dfm.service.execute.provider import Provider

from dfm.service.common.exceptions import MissingImplementation
from ._stream import Stream

from dfm.service.common.logging import getLogger


# helper
def model_dump_exclude(model: BaseModel, exclude: List[str]) -> Dict[str, Any]:
    """
    A model_dump_exclude is a function that dumps a model and excludes certain keys.
    """
    # not sure why model_dump(exclude=...) doesn't appear to work sometimes; so filtering manually
    exclude_set: Set[str] = set(exclude)
    dumped_model = model.model_dump()
    hash_base = {
        key: dumped_model[key] for key in dumped_model if key not in exclude_set
    }
    return hash_base


ProviderT = TypeVar("ProviderT", bound=Provider)
ConfT = TypeVar("ConfT", bound=AdapterConfig | None)
FunCallT = TypeVar("FunCallT", bound=FunctionCall)


class Adapter(Generic[ProviderT, ConfT, FunCallT], ABC):
    """The client essentially calls site.provider.function() and the adapter provides the
    implementation of this function for this provider at this site, possibly using some
    additional config besides just the function calls.
    Secrets are associated with the provider, not the adapter.

    Metaprogramming invariants:
    * An adapter handles exactly one type of FunctionCall
    * The adapter implementation must have __init__ parameters
      for ALL FunctionRef parameters in the FunctionCall, with the same name.
    * If a FunctionCall parameter is a List[FunctionRef] then the init parameter must
      accept a list of adapters
    * Input adapter params must be annotated as Adapter or as List[Adapter]
    * The input adapters MUST be stored in self under the same name with an underscore
      prefixed. E.g. def __init__(self, ..., dataset: Adapter): self._dataset = dataset.
      You should use the _get_input_adapter() and _set_input_adapter() methods for this
    """

    def __init__(
        self,
        dfm_request: DfmRequest,
        provider: ProviderT,
        config: ConfT,
        params: FunCallT,
    ):
        self._dfm_request = dfm_request
        self._provider = provider
        self._config = config
        self._params = params
        self._memoized_pipeline_hash: Optional[str] = None
        self._stream = None
        self._caching_iterator: Any = None
        self._logger = getLogger(
            f"{self.__class__.__name__} Adapter for function {self._params.__class__.__name__}",
            dfm_request,
        )

    # ================================
    # Metaprogramming
    # ================================
    @classmethod
    def implementation_class_name(cls) -> str:
        """
        A implementation_class_name is a function that returns the implementation class name.
        """
        module_components = cls.__module__.split(".")
        # we don't want the _filename.py in the module path for no particular reason
        # other than aestethics
        if module_components[-1].startswith("_"):
            module_components = module_components[:-1]
        module_components.append(cls.__qualname__)
        return ".".join(module_components)

    @classmethod
    def get_input_kind(cls, name: str) -> Literal["adapter", "adapter_list"] | None:
        """
        A get_input_kind is a function that returns the input kind of an adapter.
        """
        param = inspect.signature(cls.__init__).parameters[name]
        typ = param.annotation
        if inspect.isclass(typ) and issubclass(typ, Adapter):
            return "adapter"
        # typ is not a class, probably an instance of a typing object like typing.List[elem]
        # We just assume it's a list here, we don't really support anything else
        # at the moment
        if Adapter in get_args(typ):
            return "adapter_list"
        return None

    @classmethod
    def get_adapter_input_names(cls) -> List[str]:
        """
        A get_adapter_input_names is a function that returns the input names of an adapter.
        Input adapter params must be annotated as Adapter or as List[Adapter]
        """
        results = []
        for name in inspect.signature(cls.__init__).parameters.keys():
            kind = cls.get_input_kind(name)
            if kind:
                results.append(name)
        return results

    def _set_input_adapter(self, name: str, adapter: "Adapter"):
        """
        A _set_input_adapter is a function that sets the input adapter for an adapter.
        """
        setattr(self, f"_{name}", adapter)

    def _set_input_adapter_list(self, name: str, adapters: List["Adapter"]):
        """
        A _set_input_adapter_list is a function that sets the input adapter list for an adapter.
        """
        setattr(self, f"_{name}", adapters)

    def get_input_adapter(self, name: str) -> "Adapter":
        """
        A get_input_adapter is a function that returns the input adapter for an adapter.
        """
        return getattr(self, f"_{name}")

    def get_input_adapter_list(self, name: str) -> List["Adapter"]:
        """
        A get_input_adapter_list is a function that returns the input adapter list for an adapter.
        """
        return getattr(self, f"_{name}")

    # ================================
    # Basic getters
    # ================================
    @property
    def dfm_request(self) -> DfmRequest:
        return self._dfm_request

    @property
    def provider(self) -> ProviderT:
        return self._provider

    @property
    def config(self) -> ConfT:
        return self._config

    @property
    def params(self) -> FunCallT:
        return self._params

    # ================================
    # Caching
    # ================================
    @property
    def caching_iterator(self):
        return self._caching_iterator

    def _instantiate_caching_iterator(self):
        """Override if this adapter supports caching"""
        return None

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        """collect a dict that contains all information in this adapter that may affect the
        computed result. This dict will be used for computing a hash key used for caching.
        Therefore, any value that affects the output must be reflected in the dict. By default,
        this dict will contain most of the params (with a few exceptions) and nothing else.
        If the adapter configuration is important, or other conditions are important, this
        method must be overridden.
        This dict should not include the input adapters, the decision if input adapters
        are factored into the hash is done by the CachingIterator"""
        return self._collect_local_hash_dict_helper()

    def _collect_local_hash_dict_helper(
        self, exclude_params: Optional[List[str]] = None, **include_additional
    ) -> Dict[str, Any]:
        params = model_dump_exclude(
            model=self.params,
            exclude=self.get_adapter_input_names()
            + ["node_id", "is_output", "force_compute"]
            + (exclude_params if exclude_params else []),
        )
        return params | include_additional

    # ================================
    # Streams
    # ================================
    def get_or_create_stream_no_caching(self, start_if_needed: bool = True) -> Stream:
        """Creates and remembers the stream object. The adapter must be an adapter that
        doesn't use caching"""
        if not self._stream:
            if self._instantiate_caching_iterator() is not None:
                raise ServerError(
                    "get_or_create_uncached_stream() called on adapter that wants to cache"
                )
            self._stream = Stream.from_async_iterator(
                adapterclass=self.__class__.__name__,
                request_id=self.dfm_request.request_id,
                node_id=self._params.node_id,
                async_it=self.stream_body_wrapper(),
            )
        if start_if_needed and not self._stream.is_running():
            self._stream.start(stream_done_callback=self._stream_done_callback)

        return self._stream

    async def get_or_create_stream(self, start_if_needed: bool = True) -> Stream:
        """Creates and remembers the stream object. The stream is either from pre-computed
        values, if a valid cache exists, or otherwise starts the actual stream async task pumping
        values from the adapter stream_body"""
        if not self._stream:
            if not self._caching_iterator:
                try:
                    # may still return None, if this adapter doesn't support caching
                    self._caching_iterator = (
                        self._instantiate_caching_iterator()
                    )  # pylint: disable=assignment-from-none
                except Exception as ex:  # pylint: disable=broad-exception-caught
                    self._logger.exception("Error while instantiating caching iterator")
                    self._logger.exception(ex)

            if self._caching_iterator and not self.params.force_compute:
                try:
                    self._stream = (
                        await self._caching_iterator.try_creating_stream_from_cache()
                    )
                    # if this adapter is an output, send the cached values to the client
                    if self.params.is_output and self._stream:
                        async for val in self._stream:
                            to_send = await self.prepare_to_send(val)
                            self._logger.info(
                                "Adapter is output, sending cached response %s",
                                textwrap.shorten(str(to_send), width=80),
                            )
                            await self.dfm_request.send_response(
                                self.params.node_id, to_send
                            )
                except Exception as ex:  # pylint: disable=broad-exception-caught
                    self._logger.exception("Error while creating stream from cache")
                    self._logger.exception(ex)

            # couldn't load the stream from the cache, so actually starting up
            if not self._stream:
                self._stream = Stream.from_async_iterator(
                    adapterclass=self.__class__.__name__,
                    request_id=self.dfm_request.request_id,
                    node_id=self._params.node_id,
                    async_it=self.stream_body_wrapper(),
                )
                # make sure that this call comes after self._stream is set, otherwise danger
                # of infinite loop
                if self._caching_iterator:
                    # creates an async task
                    self._caching_iterator.start_caching_task()

        if start_if_needed and not self._stream.is_running():
            self._stream.start(stream_done_callback=self._stream_done_callback)

        return self._stream

    def _stream_done_callback(self, task):
        pass

    # ================================
    # Adapter body and result handling
    # ================================
    async def prepare_to_send(self, value: Any) -> ResponseBody:
        return ValueResponse(value=str(value))

    async def stream_body_wrapper(self) -> AsyncIterator[Any]:
        node_id = self.params.node_id
        try:
            await self.dfm_request.send_status(
                node_id, f"Adapter for {self.params.__class__.__name__} starting"
            )
            self._logger.info(
                "adapter.stream_body_wrapper starts iterating self.stream_body()"
            )
            async for val in self.stream_body():
                self._logger.info(
                    "adapter.stream_body_wrapper, stream_body produced a value: %s",
                    textwrap.shorten(str(val), width=80),
                )
                if self.params.is_output:
                    to_send = await self.prepare_to_send(val)
                    self._logger.info(
                        "Adapter is output, sending response %s",
                        textwrap.shorten(str(to_send), width=80),
                    )
                    await self.dfm_request.send_response(node_id, to_send)
                yield val
            self._logger.info("adapter.stream_body_wrapper, stream_body is done.")
            await self.dfm_request.send_status(
                node_id, f"Adapter for {self.params.__class__.__name__} is done"
            )
        except StopAsyncIteration:
            return
        except Exception as e:  # pylint: disable=broad-exception-caught
            self._logger.exception("stream_body_wrapper caught exception %s", e)
            await self.dfm_request.send_error(node_id, e)
            raise e

    @abstractmethod
    async def stream_body(self) -> AsyncIterator[Any]:
        # yielding some value, because this changes the type of this method from
        # Coroutine[None, None, AsyncIterator] to AsyncIterator, which is
        # what we want
        yield MissingImplementation(f"Body of adapter {self} not implemented")

    def raise_if_exception(self):
        if self._stream:
            self._stream.raise_if_exception()

    def cancel_inputs(self):
        for name in self.get_adapter_input_names():
            if self.get_input_kind(name) == "adapter_list":
                for adapter in self.get_input_adapter_list(name):
                    adapter.cancel()
            else:
                self.get_input_adapter(name).cancel()

    def cancel(self):
        self.cancel_inputs()
        if self._caching_iterator:
            self._caching_iterator.cancel()
        if self._stream:
            self._stream.cancel()
            self._stream = None

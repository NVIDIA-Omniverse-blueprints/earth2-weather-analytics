# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Dict, List

from pydantic import UUID4

from dfm.service.common.request import DfmRequest
from dfm.api import FunctionCall
from dfm.common import Advise
from dfm.service.common.exceptions import DataError
from dfm.service.execute import Site
from dfm.service.execute.provider import UninitializedAdapter
from dfm.service.execute.adapter import Adapter


def _get_from_symtable(
    sym_table: Dict[UUID4, UninitializedAdapter],
    node_id: UUID4,
    name: str,
    params: FunctionCall,
) -> Adapter:
    if node_id not in sym_table:
        raise DataError(
            f"Node with id {node_id} not found."
            f" Referenced in param {name} of {params}"
        )
    return sym_table[node_id].adapter_instance


def _resolve_input_refs(
    uninitialized: UninitializedAdapter,
    params: FunctionCall,
    sym_table: Dict[UUID4, UninitializedAdapter],
) -> Dict[str, Adapter | List[Adapter]]:
    """Go through the adapter inputs of the uninitialized adapter, find their UUIDs in the
    FunctionCall, and look the UUIDs up in the symbol table; essentially, replace the UUIDs
    with the corresponding adapter object instances"""
    input_refs: Dict[str, Adapter | List[Adapter]] = {}
    for name in uninitialized.get_adapter_input_names():
        node_ids = getattr(params, name)
        if isinstance(node_ids, list):
            assert uninitialized.get_input_kind(name) == "adapter_list"
            refs = [
                _get_from_symtable(sym_table, node_id, name, params)
                for node_id in node_ids
            ]
            input_refs[name] = refs
        else:
            assert uninitialized.get_input_kind(name) == "adapter"
            ref = _get_from_symtable(sym_table, node_ids, name, params)
            input_refs[name] = ref
    return input_refs


def _remove_all_from_set(
    inputs: Dict[str, Adapter | List[Adapter]], adapter_set: set[Adapter]
):
    for adapters in inputs.values():
        if isinstance(adapters, list):
            for adapter in adapters:
                if adapter in adapter_set:
                    adapter_set.remove(adapter)
        else:
            # single adapter input
            if adapters in adapter_set:
                adapter_set.remove(adapters)


def pipeline_dict_to_adapter_graph(
    site: Site, dfm_request: DfmRequest, pipeline: Dict[UUID4, FunctionCall]
) -> List[Adapter]:
    # If an adapter takes another adapter as an input, we want to pass this other adapter
    # as a reference to the __init__(). We could try to sort the pipeline to make sure that if
    # adapter B uses A, that A was instantiated before. Instead of sorting, we take a different
    # approach: in the first pass, we create the adapter objects without calling the init methods
    # ensuring we have all adapter objects. And then we call init in the second pass.
    # This way, the init methods look nice because they directly receive the
    # input adapters (e.g. makes writing tests easier)
    sym_table: Dict[UUID4, UninitializedAdapter] = {}
    # optimistically assume, all adapters are leaves at first
    leaves: set[Adapter] = set()
    for node_id, func_params in pipeline.items():
        uninitialized = site.pre_instantiate_adapter(dfm_request, func_params)
        sym_table[node_id] = uninitialized
        leaves.add(uninitialized.adapter_instance)

    # finalize initialization of the adapters, giving them a chance to hook up with each other

    for node_id, uninitialized in sym_table.items():
        params = uninitialized.params
        # collect the (possibly still uninitialized, because we are not iterating in any
        # particular order) input adapter objects that are input
        # for this adapter, so we can initialize this adapter
        input_refs = _resolve_input_refs(uninitialized, params, sym_table)
        # all inputs are used and aren't leaves
        _remove_all_from_set(input_refs, leaves)
        # finish initialization of this adapter
        uninitialized.finish_init(input_adapters=input_refs)

    if len(leaves) == 0:
        raise DataError("Pipeline does not have any leave operations")

    # Note: if we ever want to do more complex stuff, we can perform peephole optimizations here
    # sinks = [adapter.peephole() for adapter in sinks]

    # we return the leaves and initiate execution backwards.
    return list(leaves)


def pipeline_dict_to_discovery_adapters(
    site: Site, dfm_request: DfmRequest, pipeline: Dict[UUID4, FunctionCall]
) -> Dict[UUID4, Adapter | List[Adapter]]:
    """
    Returns a single adapter for each FunctionCall (represented by its UUID)
    if the provider was given by the client, or a list of adapters
    of length 0 or more if provider was set to Advise()"""

    def initialize_adapter_helper(uninitialized_adapter: UninitializedAdapter):
        # we don't really hook up the adapters during discovery, so just set to None
        input_adapters: Dict[str, None] = {
            name: None
            for name in uninitialized_adapter.adapter_instance.get_adapter_input_names()
        }
        return uninitialized_adapter.finish_init(input_adapters)  # type: ignore

    result: Dict[UUID4, Adapter | List[Adapter]] = {}
    for node_id, func_params in pipeline.items():
        if isinstance(func_params.provider, Advise):
            uninitialized_list = site.pre_initialize_adapters_without_provider(
                dfm_request, func_params
            )
            # if we didn't find any adapters, list will be empty
            initialized_list = [
                initialize_adapter_helper(ua) for ua in uninitialized_list
            ]
            result[node_id] = initialized_list
        else:
            uninitialized_adapter = site.pre_instantiate_adapter(
                dfm_request, func_params
            )
            initialized_adapter = initialize_adapter_helper(uninitialized_adapter)
            result[node_id] = initialized_adapter

    return result

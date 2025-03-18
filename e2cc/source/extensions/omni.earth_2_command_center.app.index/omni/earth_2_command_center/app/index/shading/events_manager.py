# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import carb.events
import omni.usd
from pxr import Sdf, Usd


class EventsManager:
    """Handles IndeX data loaders within a stage."""

    _events: dict[str, str]
    _stage_events_sub: carb.events.ISubscription

    def __init__(self):
        self._events = {}

    def _apply_events(self, stage: Usd.Stage):
        cld = stage.GetRootLayer().customLayerData
        # FIXME: Keep only the 4 first events as a limitation from the IndeX USD integration
        # https://jirasw.nvidia.com/browse/NVIDX-1347
        eventsnames = ["timestep", "timestep2", "timestep3", "timestep4"]
        namedevents = dict(zip(eventsnames, self._events.values()))

        cld["nvindex:configuration"] = cld.get("nvindex:configuration", {}) | {"events": namedevents}
        stage.GetRootLayer().customLayerData = cld

    def register_update_event(self, stage: Usd.Stage, name: str, path: Sdf.Path):
        assert name not in self._events

        self._events[
            name
        ] = f"""{{
            "$COMMENT": "Link Kit animation playback to timestep selection.",
            "jsonrpc": "2.0",
            "id": 0,
            "method": "nv::index::plugin::openvdb_integration::command_receiver.NVDB_GDS_update_compute_task",
            "params": {{
                "compute_task_name": "{path}",
                "compute_task_mode":      1,
                "active_time_step":       ${{TIMESTEP}},
                "upload_multi_thread":    false,
                "nb_upload_threads":      1,
                "logging":                true
            }}
        }}
        """
        self._apply_events(stage)

    def unregister_event(self, stage: Usd.Stage, name: str):
        del self._events[name]
        self._apply_events(stage)

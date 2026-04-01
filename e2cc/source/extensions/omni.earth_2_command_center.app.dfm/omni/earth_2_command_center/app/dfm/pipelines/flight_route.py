# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import carb
import omni.kit.async_engine as async_engine
from functools import partial
from datetime import datetime, timezone
from uuid import UUID

from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalClient, SignalAllDone
from dfm.api.response import ValueResponse

try:
    from dfm.api.data_loader import LoadEra5ModelData
except ImportError:
    carb.log_warning("ERA5/GFS adapter is not available")
    LoadEra5ModelData = None

try:
    from dfm.api.aviation import ExtractRouteWeather, ScoreRouteHazards
except ImportError:
    carb.log_warning("Aviation route adapters not available")
    ExtractRouteWeather = None
    ScoreRouteHazards = None

from ..utils import run_pipeline
from ._base import PipelineBase


# Variables needed for route weather extraction
ROUTE_INPUT_VARS = [
    "u200", "v200", "u300", "v300", "u500", "v500",
    "u700", "v700", "u850", "v850",
    "t300", "t500", "t700", "t850",
    "r500", "r700", "r850",
]


class FlightRoutePipeline(PipelineBase):

    @staticmethod
    def name():
        return "Flight Route Weather"

    @staticmethod
    def _create_pipeline(
        waypoints: list,
        departure_time: str,
        date: datetime,
        provider: str = "gfs",
        ground_speed_kts: float = 450.0,
        variables: list = None,
    ) -> Process:
        """Build a pipeline that loads gridded data and extracts weather along a route."""
        if LoadEra5ModelData is None:
            raise ImportError("ERA5/GFS adapter is not available")
        if ExtractRouteWeather is None:
            raise ImportError("Aviation route adapters are not available")

        extract_vars = variables or ROUTE_INPUT_VARS

        with Process() as pipeline:
            # Load pressure-level data
            data = LoadEra5ModelData(
                provider=provider,
                variables=ROUTE_INPUT_VARS,
                selection={"time": date.isoformat()},
            )

            # Extract weather along route
            route_weather = ExtractRouteWeather(
                data=data,
                waypoints=waypoints,
                departure_time=departure_time,
                ground_speed_kts=ground_speed_kts,
                variables=extract_vars,
            )

            # Score hazards
            scored = ScoreRouteHazards(
                data=route_weather,
                is_output=True,
            )

            # Signal completion
            SignalAllDone(
                node_id=well_known_id("all_done"),
                after=[scored],
                message="done",
            )

        carb.log_info(pipeline)
        return pipeline

    @classmethod
    def pipeline_callback(
        cls, node_id: UUID, response: ValueResponse, waypoints: list
    ) -> None:
        if response.value == "done":
            carb.log_info("Flight Route Pipeline is finished")
            return

        carb.log_info(f"Flight Route result received: {type(response.value)}")
        # Route results are returned as ValueResponse with the scored dataset
        # The UI extension will handle visualization

    @classmethod
    def execute(
        cls,
        waypoints: list,
        departure_time: str,
        dateobj: datetime,
        dfm_url: str = "http://localhost:8080",
        provider: str = "gfs",
        ground_speed_kts: float = 450.0,
        variables: list = None,
    ):
        if len(waypoints) < 2:
            raise ValueError("Route must have at least 2 waypoints")

        pipeline = cls._create_pipeline(
            waypoints, departure_time, dateobj, provider=provider,
            ground_speed_kts=ground_speed_kts, variables=variables,
        )
        callback = partial(cls.pipeline_callback, waypoints=waypoints)
        promise = async_engine.run_coroutine(
            run_pipeline(pipeline, callback, dfm_url)
        )
        return promise

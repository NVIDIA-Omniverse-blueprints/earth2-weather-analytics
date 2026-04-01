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
from uuid import UUID

from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalAllDone
from dfm.api.response import ValueResponse

try:
    from dfm.api.aviation import LoadMetarData, LoadTafData, LoadPirepData, LoadSigmetData
except ImportError:
    carb.log_warning("Aviation data loaders not available")
    LoadMetarData = None
    LoadTafData = None
    LoadPirepData = None
    LoadSigmetData = None

from ..utils import run_pipeline
from ._base import PipelineBase


class MetarStationsPipeline(PipelineBase):

    @staticmethod
    def name():
        return "METAR Stations"

    @staticmethod
    def _create_pipeline(
        stations: list = None,
        bbox: str = None,
    ) -> Process:
        """Build a pipeline that loads METAR observations."""
        if LoadMetarData is None:
            raise ImportError("Aviation METAR adapter is not available")

        with Process() as pipeline:
            metar = LoadMetarData(
                provider="awc",
                is_output=True,
                stations=stations,
                bbox=bbox,
                return_geojson=True,
                return_meta_data=True,
            )

            SignalAllDone(
                node_id=well_known_id("all_done"),
                after=[metar],
                message="done",
            )

        carb.log_info(pipeline)
        return pipeline

    @classmethod
    def pipeline_callback(cls, node_id: UUID, response: ValueResponse) -> None:
        if response.value == "done":
            carb.log_info("METAR Pipeline is finished")
            return

        carb.log_info(f"METAR data received: {type(response.value)}")

    @classmethod
    def execute(
        cls,
        stations: list = None,
        bbox: str = None,
        dfm_url: str = "http://localhost:8080",
    ):
        pipeline = cls._create_pipeline(stations=stations, bbox=bbox)
        callback = cls.pipeline_callback
        promise = async_engine.run_coroutine(
            run_pipeline(pipeline, callback, dfm_url)
        )
        return promise


class PirepPipeline(PipelineBase):

    @staticmethod
    def name():
        return "Pilot Reports"

    @staticmethod
    def _create_pipeline(bbox: str = None, age_hours: int = 2) -> Process:
        if LoadPirepData is None:
            raise ImportError("Aviation PIREP adapter is not available")

        with Process() as pipeline:
            pirep = LoadPirepData(
                provider="awc",
                is_output=True,
                bbox=bbox,
                age_hours=age_hours,
                return_geojson=True,
                return_meta_data=True,
            )
            SignalAllDone(
                node_id=well_known_id("all_done"),
                after=[pirep],
                message="done",
            )
        return pipeline

    @classmethod
    def pipeline_callback(cls, node_id: UUID, response: ValueResponse) -> None:
        if response.value == "done":
            carb.log_info("PIREP Pipeline is finished")
            return

    @classmethod
    def execute(cls, bbox: str = None, age_hours: int = 2, dfm_url: str = "http://localhost:8080"):
        pipeline = cls._create_pipeline(bbox=bbox, age_hours=age_hours)
        promise = async_engine.run_coroutine(
            run_pipeline(pipeline, cls.pipeline_callback, dfm_url)
        )
        return promise


class SigmetPipeline(PipelineBase):

    @staticmethod
    def name():
        return "SIGMET/AIRMET"

    @staticmethod
    def _create_pipeline(hazard_type: str = "sigmet") -> Process:
        if LoadSigmetData is None:
            raise ImportError("Aviation SIGMET adapter is not available")

        with Process() as pipeline:
            sigmet = LoadSigmetData(
                provider="awc",
                is_output=True,
                hazard_type=hazard_type,
                return_geojson=True,
                return_meta_data=True,
            )
            SignalAllDone(
                node_id=well_known_id("all_done"),
                after=[sigmet],
                message="done",
            )
        return pipeline

    @classmethod
    def pipeline_callback(cls, node_id: UUID, response: ValueResponse) -> None:
        if response.value == "done":
            carb.log_info("SIGMET Pipeline is finished")
            return

    @classmethod
    def execute(cls, hazard_type: str = "sigmet", dfm_url: str = "http://localhost:8080"):
        pipeline = cls._create_pipeline(hazard_type=hazard_type)
        promise = async_engine.run_coroutine(
            run_pipeline(pipeline, cls.pipeline_callback, dfm_url)
        )
        return promise

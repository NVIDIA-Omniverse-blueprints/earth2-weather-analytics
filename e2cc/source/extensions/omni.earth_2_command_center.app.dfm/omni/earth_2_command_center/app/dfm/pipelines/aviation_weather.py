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
from datetime import datetime, timezone, timedelta
from uuid import UUID

from dfm.api import Process, well_known_id, FunctionCall
from dfm.api.dfm import SignalAllDone, TextureFile
from dfm.api.xarray import ConvertToUint8, RenderUint8ToImages
from dfm.api.response import ValueResponse

try:
    from dfm.api.data_loader import LoadEra5ModelData
except ImportError:
    carb.log_warning("ERA5/GFS adapter is not available in the installed DFM client package")
    LoadEra5ModelData = None

try:
    from dfm.api.aviation import ComputeWindShear, ComputeEllrodIndex, ComputeIcingProbability
except ImportError:
    carb.log_warning("Aviation adapters not available in the installed DFM client package")
    ComputeWindShear = None
    ComputeEllrodIndex = None
    ComputeIcingProbability = None

from ..utils import create_dfm_image_feature, run_pipeline
from ..utils.constants import VARIABLE_CMAP, VARIABLE_RANGE, VARIABLE_UNIT, VARIABLE_LABELS
from ..utils.exceptions import InputVariableError, InputTimeRangeError
from ._base import PipelineBase


# Aviation variable -> required ERA5/GFS input variables
AVIATION_INPUT_VARS = {
    "wind_shear": ["u200", "v200", "u300", "v300", "u500", "v500", "u700", "v700", "u850", "v850"],
    "ellrod_ti": ["u200", "v200", "u250", "v250", "u300", "v300", "u500", "v500"],
    "icing_prob": ["t500", "t700", "t850", "r500", "r700", "r850"],
}

# Aviation variable -> computation FunctionCall class
AVIATION_COMPUTE_CLS = {
    "wind_shear": ComputeWindShear,
    "ellrod_ti": ComputeEllrodIndex,
    "icing_prob": ComputeIcingProbability,
}


class AviationWeatherPipeline(PipelineBase):

    @staticmethod
    def name():
        return "Aviation Weather"

    @staticmethod
    def _create_pipeline(
        variable: str,
        date: datetime,
        provider: str = "gfs",
        num_timesteps: int = 4,
        step_size_h: int = 6,
    ) -> Process:
        """Build a pipeline that loads ERA5/GFS data and applies aviation computation."""
        if LoadEra5ModelData is None:
            raise ImportError("ERA5/GFS adapter is not available")

        compute_cls = AVIATION_COMPUTE_CLS.get(variable)
        if compute_cls is None:
            raise InputVariableError(f"Unknown aviation variable: {variable}")

        input_vars = AVIATION_INPUT_VARS[variable]
        min_value = VARIABLE_RANGE[variable][0]
        max_value = VARIABLE_RANGE[variable][1]

        delta = timedelta(hours=step_size_h)

        with Process() as pipeline:
            wait_list = []
            current_time = date

            for _ in range(num_timesteps):
                # Load pressure level data
                data = LoadEra5ModelData(
                    provider=provider,
                    variables=input_vars,
                    selection={"time": current_time.isoformat()},
                )

                # Apply aviation computation
                computed = compute_cls(data=data, output_name=variable)

                # Create diffuse and alpha textures
                for texture in ["diffuse", "alpha"]:
                    tex = ConvertToUint8(
                        data=computed,
                        time_dimension="time",
                        xydims=("lon", "lat"),
                        min=min_value,
                        max=max_value,
                    )

                    render_images = RenderUint8ToImages(
                        provider="local_earth2_textures",
                        is_output=True,
                        data=tex,
                        time_dimension="time",
                        xydims=("lon", "lat"),
                        variable=variable,
                        return_meta_data=True,
                        return_image_data=False,
                        additional_meta_data={
                            "variable": variable,
                            "texture": texture,
                        },
                    )
                    wait_list.append(render_images)

                current_time += delta

            SignalAllDone(
                node_id=well_known_id("all_done"),
                after=wait_list,
                message="done",
            )

        carb.log_info(pipeline)
        return pipeline

    @classmethod
    def pipeline_callback(
        cls, node_id: UUID, response: ValueResponse, variable: str, dateobj: datetime
    ) -> None:
        if response.value == "done":
            carb.log_info("Aviation Weather Pipeline is finished")
            return

        api_class = (
            response.value.get("api_class", "unknown")
            if isinstance(response.value, dict)
            else "unknown"
        )
        if api_class == "dfm.api.dfm.TextureFile":
            texture = TextureFile.model_validate(response.value)
        else:
            raise ValueError(
                f"expected TextureFile, got api_class {api_class}, response {response}"
            )

        actual_variable = (
            texture.metadata.get("variable", variable) if texture.metadata else variable
        )
        variable_label = VARIABLE_LABELS.get(actual_variable, actual_variable)

        meta_data = {
            "variable_label": variable_label,
            "source_label": "Aviation",
            "type_label": "derived",
            "date_time": dateobj,
            "cmap_label": VARIABLE_CMAP[actual_variable],
            "cmap_min": VARIABLE_RANGE[actual_variable][0],
            "cmap_max": VARIABLE_RANGE[actual_variable][1],
            "cmap_unit": VARIABLE_UNIT[actual_variable],
        }

        if texture.metadata:
            meta_data.update(texture.metadata)

        try:
            timestamp = datetime.strptime(texture.timestamp, "%Y-%m-%dT%H:%M")
        except ValueError:
            timestamp = datetime.strptime(texture.timestamp, "%Y-%m-%dT%HC%M")
        if not timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        name = f"Aviation {variable_label} {dateobj.isoformat()}"
        if texture.metadata.get("texture") == "diffuse":
            create_dfm_image_feature(
                [texture.url], [], [timestamp], name, meta_data,
                cmap=VARIABLE_CMAP[actual_variable],
            )
        else:
            create_dfm_image_feature(
                [], [texture.url], [timestamp], name, meta_data,
                cmap=VARIABLE_CMAP[actual_variable],
            )

    @classmethod
    def input_validation(cls, variables: list[str], dateobj: datetime) -> None:
        valid_vars = set(AVIATION_INPUT_VARS.keys())
        invalid = set(variables) - valid_vars
        if invalid:
            raise InputVariableError(
                f"Invalid aviation variable(s): {', '.join(invalid)}. "
                f"Valid: {', '.join(valid_vars)}"
            )

        if dateobj > datetime.now():
            raise InputTimeRangeError("Cannot request future dates for aviation weather")

    @classmethod
    def execute(
        cls,
        variable: str,
        dateobj: datetime,
        dfm_url: str = "http://localhost:8080",
        num_timesteps: int = 4,
        provider: str = "gfs",
    ):
        cls.input_validation([variable], dateobj)
        pipeline = cls._create_pipeline(
            variable, dateobj, provider=provider, num_timesteps=num_timesteps, step_size_h=6
        )
        callback = partial(cls.pipeline_callback, variable=variable, dateobj=dateobj)
        promise = async_engine.run_coroutine(run_pipeline(pipeline, callback, dfm_url))
        return promise

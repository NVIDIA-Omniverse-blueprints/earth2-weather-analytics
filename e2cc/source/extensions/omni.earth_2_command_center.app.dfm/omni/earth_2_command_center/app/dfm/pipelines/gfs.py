# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



import datetime
import os
from uuid import UUID
import carb
import omni.kit.async_engine as async_engine
from functools import partial
from datetime import datetime, timezone, timedelta

# Import DFM API and client packages that can be used to build and run pipelines.
from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalAllDone, TextureFile
try:
    from dfm.api.data_loader import LoadEra5ModelData
except ImportError:
    carb.log_warning("ERA5/GFS adapter is not available in the installed DFM client package")
    LoadEra5ModelData = None
from dfm.api.xarray import ConvertToUint8, RenderUint8ToImages, VariableNorm
from dfm.api.response import ValueResponse

from ..utils import create_dfm_image_feature, run_pipeline
from ..utils.constants import VARIABLE_CMAP, VARIABLE_RANGE, VARIABLE_UNIT, VARIABLE_LABELS
from ..utils.exceptions import InputVariableError, InputTimeRangeError

from ._base import PipelineBase

class GFSPipeline(PipelineBase):

    @staticmethod
    def name():
        return "Global Forecast System"

    @staticmethod
    def _create_pipeline(
        variable: str, date: datetime, provider: str = "gfs", num_timesteps: int = 1, step_size_h: int = 6
    ) -> Process:
        """
        A helper function that uses provided settings to build a pipeline.
        """
        # Check for required adapters
        if LoadEra5ModelData is None:
            import dfm
            raise ImportError(
                f"ERA5/GFS adapter is not available in the installed DFM package (version {dfm.__version__}). "
                "To update the package, replace the wheel in deps/wheels and delete the _build folder "
                "then rebuild from scratch."
            )

        force_loader_compute = False  # Controls loader cache.
        force_texture_compute = False  # Controls texture cache.

        # Handle wind components
        variables = ["u10m", "v10m"] if variable == "w10m" else [variable]

        delta = timedelta(hours=step_size_h)
        # Here we start building the pipeline object.
        # Please notice that we don't perform any data processing here,
        # This code only builds a description of the processing that will
        # happen inside DFM site.
        # FunctionCall.set_allow_outside_block()
        with Process() as pipeline:
            wait_list = []
            current_time: datetime = date
            for _ in range(num_timesteps):
                # Load data from configured provider
                data = LoadEra5ModelData(
                    provider=provider,
                    variables=variables,
                    selection={"time": current_time.isoformat()},
                    force_compute=force_loader_compute,
                )

                # For each variable, create a texture
                for var in variables:
                    min_value = VARIABLE_RANGE[var][0]
                    max_value = VARIABLE_RANGE[var][1]
                    for texture in ["diffuse", "alpha"]:
                        # For wind components, we need to normalize the data to get a centered alpha texture
                        if texture == "alpha" and variable=="w10m":
                            data_norm = VariableNorm(
                                    data=data,
                                    variables=[var],
                                    p=1,
                                    output_name=var
                                )
                            # Scale values to UINT8 range
                            tex = ConvertToUint8(
                                data=data_norm,
                                time_dimension="time",
                                xydims=("lon", "lat"),
                                min=1,
                                max=max_value,
                            )
                        else:
                            # Scale values to UINT8 range
                            tex = ConvertToUint8(
                                data=data,
                                time_dimension="time",
                                xydims=("lon", "lat"),
                                min=min_value,
                                max=max_value,
                            )

                        # Convert the scaled data to a grayscale image
                        render_images = RenderUint8ToImages(
                            provider="local_earth2_textures",
                            is_output=True,
                            data=tex,
                            time_dimension="time",
                            xydims=("lon", "lat"),
                            variable=var,  # Specify which variable to render
                            force_compute=force_texture_compute,
                            return_meta_data=True,
                            return_image_data=False,
                            additional_meta_data={"variable": var, "texture": texture}  # Add variable to metadata
                        )
                        wait_list.append(render_images)
                current_time += delta

            # Send 'all_done' signal when processing is done
            SignalAllDone(
                node_id=well_known_id("all_done"),
                after=wait_list,
                message="done"
            )

        # Return the pipeline object.
        carb.log_info(pipeline)
        return pipeline

    @classmethod
    def pipeline_callback(cls, node_id: UUID, response: ValueResponse, variable: str, dateobj: datetime) -> None:
        """Pipeline call back after successful response

        Parameters
        ----------
        response : ValueResponse
            DFM Response object
        variable : str
            Variable retrieved
        dateobj : datetime
            Data object of fetch
        """
        if response.value == 'done':
            carb.log_info("GFS Pipeline is finished")
            return

        api_class = response.value.get('api_class', 'unknown') if isinstance(response.value, dict) else 'unknown'
        if api_class == 'dfm.api.dfm.TextureFile':
            texture: TextureFile = TextureFile.model_validate(response.value)
        else:
            raise ValueError(f"expected TextureFile class here, got api_class {api_class}, response {response}")

        # Get the actual variable from metadata if it exists (for wind components)
        actual_variable = texture.metadata.get("variable", variable) if texture.metadata else variable
        variable_label = VARIABLE_LABELS[actual_variable] if actual_variable in VARIABLE_LABELS else actual_variable

        # Create meta data needed by the blueprint API
        meta_data = {
            "variable_label": variable_label,
            "source_label": "GFS",
            "type_label": "forecast",
            "date_time": dateobj,
            "cmap_label": VARIABLE_CMAP[actual_variable],
            "cmap_min": VARIABLE_RANGE[actual_variable][0],
            "cmap_max": VARIABLE_RANGE[actual_variable][1],
            "cmap_unit": VARIABLE_UNIT[actual_variable]
        }

        if texture.metadata:
            meta_data.update(texture.metadata)

        try:
            timestamp = datetime.strptime(texture.timestamp, "%Y-%m-%dT%H:%M")
        except ValueError:
            timestamp = datetime.strptime(texture.timestamp, "%Y-%m-%dT%HC%M")
        if not timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        name = f"GFS {actual_variable} {dateobj.isoformat()}"
        if texture.metadata.get("texture") == "diffuse":
            create_dfm_image_feature([texture.url], [], [timestamp], name, meta_data, cmap=VARIABLE_CMAP[actual_variable])
        else:
            create_dfm_image_feature([], [texture.url], [timestamp], name, meta_data, cmap=VARIABLE_CMAP[actual_variable])

    @classmethod
    def input_validation(cls, variables: list[str], dateobj: datetime) -> None:
        """Offline check input requests

        Check the DFM code, for look for advice decorators,

        Parameters
        ----------
        variables : list[str]
            List of variables to fetch
        dateobj : str
            Date time object to fetch

        Raises
        ------
        ValueError
            If invalid inputs
        """
        if not (dateobj - datetime(1900, 1, 1)).total_seconds() % 21600 == 0:
            raise InputTimeRangeError(
                f"Requested date time {dateobj}Z needs to be 6 hour interval (UTC) for GFS"
            )

        if dateobj > datetime.now():
            raise InputTimeRangeError(f"Cannot have a future date time for GFS request")

        # Check if date is more than 3.5 years in the past, seems this GFS bucket slowly deletes old data
        cutoff_date = datetime.now() - timedelta(days=int(3.5 * 365))
        if dateobj < cutoff_date:
            raise InputTimeRangeError(
                f"Requested date time {dateobj}Z needs to be within the last 3.5 years (UTC) for GFS"
            )

        if len(set(variables)-set(["w10m", "u10m", "v10m", "t2m", "tcwv"])):
            carb.log_error(f"Invalid requested variables {variables}")
            raise InputVariableError(f"Invalid requested variable(s) {', '.join([VARIABLE_LABELS[var] for var in variables])} for GFS")

    @classmethod
    def execute(cls, variable: str, dateobj: datetime, dfm_url: str = "http://localhost:8080", num_timesteps: int = 1):
        """Sync execute script for GFS pipeline

        Parameters
        ----------
        variable : str
            Variable to fetch
        dateobj : datetime
            ISO formated datetime string
        dfm_url : str, optional
            URL of running DFM server, by default "http://localhost:8080"

        Returns
        -------
        Future[Any]
            future of the running coroutine the pipeline is executed in
        """
        # Input validation
        cls.input_validation([variable], dateobj)

        # Create single pipeline
        pipeline = cls._create_pipeline(variable, dateobj, num_timesteps=num_timesteps, step_size_h=6)
        # Returns a asyncio task
        callback = partial(cls.pipeline_callback, variable=variable, dateobj=dateobj)
        promise = async_engine.run_coroutine(run_pipeline(pipeline, callback, dfm_url))

        return promise

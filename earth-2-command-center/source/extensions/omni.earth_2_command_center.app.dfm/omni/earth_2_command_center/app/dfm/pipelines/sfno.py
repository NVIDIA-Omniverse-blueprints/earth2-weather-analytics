# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import json

from datetime import datetime, timezone, timedelta
from functools import partial
from typing import Any

import carb
import omni.kit.async_engine as async_engine

from dfm.api import Pipeline, Yield, PlaceParam, StopToken
from federation.api import TextureFile, TextureFileList

# Import adapters with error handling
try:
    from federation.fed.api.earth2 import SfnoPrognostic
except ImportError:
    carb.log_warning("SfnoPrognostic adapter is not available in the installed DFM client package")
    SfnoPrognostic = None
from federation.fed.api.earth2 import LoadGfsEra5Data, ConvertToUint8, RenderUint8ToImages, VariableNorm


from ..utils import create_dfm_image_feature, run_pipeline
from ..utils.constants import VARIABLE_CMAP, VARIABLE_LABELS, VARIABLE_RANGE, VARIABLE_UNIT
from ..utils.exceptions import InputVariableError, InputTimeRangeError

from ._base import PipelineBase



class SfnoPrognosticPipeline(PipelineBase):

    @staticmethod
    def name():
        return "Sfno Prognostic"

    @classmethod
    def _create_pipeline(
        cls, variable: str, date: datetime, num_timesteps: int = 1, site: str = "homesite",
        return_image_data: bool = True,
    ) -> tuple[Pipeline, list[dict[str, Any]], list[str]]:
        """
        Build a DFM pipeline for Sfno Prognostic data processing.

        Creates a pipeline that fetches initial conditions from GFS and runs Sfno Prognostic for num_timesteps,
        applies normalization and scaling, and renders the data as JPEG textures for each timestep.

        Parameters
        ----------
        variable : str
            Climate variable to process (e.g., 'w10m', 't2m', 'tp', etc.)
        date : datetime
            Starting datetime for data retrieval (2021-01-01 to present)
        num_timesteps : int, optional
            Number of timesteps to process (default: 1)
        site : str, optional
            DFM site identifier (default: "homesite")
        return_image_data : bool, optional
            Whether to return image data (default: False)

        Returns
        -------
        tuple[Pipeline, list[dict[str, Any]], list[str]]
            Pipeline object, input parameters, and yield place names
        """
        # Check for required adapters
        if SfnoPrognostic is None:
            import dfm
            raise ImportError(
                f"SfnoPrognostic adapter is not available in the installed DFM package (version {dfm.__version__}). "
                "To update the package, replace the wheel in deps/wheels and delete the _build folder "
                "then rebuild from scratch."
            )

        # Here we start building the pipeline object.
        # Please notice that we don't perform any data processing here,
        # This code only builds a description of the processing that will
        # happen inside DFM site.

        places = []
        seed=1337
        device="cuda"

        with Pipeline() as pipeline:
            gfs = LoadGfsEra5Data(
                site=site,
                variables=["*"],
                selection=json.dumps({"time": date.isoformat(), "mode": "aws"}),
            )
            sfno = SfnoPrognostic(
                site=site,
                dataset=gfs,
                n_steps=num_timesteps,
                seed=seed,
                device=device,
            )

            # Handle wind components
            variables = ["u10m", "v10m"] if variable == "w10m" else [variable]

            for var in variables:
                min_value = VARIABLE_RANGE[var][0]
                max_value = VARIABLE_RANGE[var][1]
                for texture in ["diffuse", "alpha"]:
                    # For wind components, we need to normalize the data to get a centered alpha texture
                    if texture == "alpha" and variable == "w10m":
                        data_norm = VariableNorm(
                            site=site,
                            data=sfno,
                            variables=[var],
                            p=1,
                            output_name=var,
                        )
                        # Scale values to UINT8 range
                        tex = ConvertToUint8(
                            site=site,
                            data=data_norm,
                            time_dimension="time",
                            xydims=["lon", "lat"],
                            min_value=1, # clip bottom to get more transparent
                            max_value=max_value,
                        )
                    else:
                        # Scale values to UINT8 range
                        tex = ConvertToUint8(
                            site=site,
                            data=sfno,
                            time_dimension="time",
                            xydims=["lon", "lat"],
                            min_value=min_value,
                            max_value=max_value,
                        )

                    render_uint8_to_images = RenderUint8ToImages(
                        site=site,
                        data=tex,
                        variable=var,
                        xydims=["lon", "lat"],
                        time_dimension="time",
                        additional_meta_data=json.dumps({"variable": var, "texture": texture}),
                        return_meta_data=True,
                        return_image_data=return_image_data,
                        format="jpeg",
                    )
                    place = f"yield_{texture}_{var}"
                    places.append(place)
                    Yield(value=render_uint8_to_images, place=place)

        # Prepare input parameters
        input_params = []
        return pipeline, input_params, places

    @classmethod
    def pipeline_callback(cls,
                          response: Any,
                          variable: str,
                          dateobj: datetime,
                          num_timesteps: int) -> None:
        """
        Process Sfno Prognostic pipeline response and create DFM image features.

        Handles the results from the  Sfno Prognostic pipeline execution, extracting texture
        files and creating image features to visualize the generated data.

        Parameters
        ----------
        response : Any
            Pipeline response containing texture files or stop token
        variable : str
            Original requested climate variable name
        dateobj : datetime
            Original requested datetime for historical data
        num_timesteps : int
            Number of timesteps to process
        Returns
        -------
        None
        """

        carb.log_info(f"cBottle Tropical Cyclone Guidance - Video Pipeline callback received response: {response}")
        if isinstance(response, StopToken):
            carb.log_info("cBottle Tropical Cyclone Guidance - Video Pipeline is finished")
            return

        assert isinstance(response, TextureFileList)
        assert len(response.texture_files) == num_timesteps + 1
        for texture in response.texture_files:
            # Get the actual variable from metadata if it exists (for wind components)
            actual_variable = texture.metadata.get("variable", variable) if texture.metadata else variable
            variable_label = VARIABLE_LABELS[actual_variable] if actual_variable in VARIABLE_LABELS else actual_variable
            timestamp = datetime.strptime(texture.timestamp, "%Y-%m-%dT%H:%M")
            if not timestamp.tzinfo:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            # Create meta data needed by the blueprint API
            meta_data = {
                "variable_label": variable_label,
                "source_label": "Sfno Prognostic",
                "type_label": "forecast",
                "date_time": dateobj,
                "cmap_label": VARIABLE_CMAP[actual_variable],
                "cmap_min": VARIABLE_RANGE[actual_variable][0],
                "cmap_max": VARIABLE_RANGE[actual_variable][1],
                "cmap_unit": VARIABLE_UNIT[actual_variable],
            }

            if texture.metadata:
                meta_data.update(texture.metadata)

            name = f"Sfno Prognostic {actual_variable} {dateobj.isoformat()}"

            if texture.metadata.get("texture") == "diffuse":
                create_dfm_image_feature(
                    [texture.url], [], [timestamp], name, meta_data, cmap=VARIABLE_CMAP[actual_variable], is_full_globe=False
                )
            else:
                create_dfm_image_feature(
                    [], [texture.url], [timestamp], name, meta_data, cmap=VARIABLE_CMAP[actual_variable], is_full_globe=False
                )


    @classmethod
    def input_validation(cls, variables: list[str], dateobj: datetime) -> None:
        """Validate input parameters for Sfno Prognostic pipeline

        Validates that the requested variables and datetime are supported by the Sfno Prognostic data source.

        Parameters
        ----------
        variables : list[str]
            List of variables to fetch (must be from: w10m, u10m, v10m, t2m, tp, tcwv)
        dateobj : datetime
            Datetime object to fetch (must be daily intervals from 2021-01-01 to present)

        Raises
        ------
        InputTimeRangeError
            If datetime is outside valid range or not on daily intervals
        InputVariableError
            If variables are not supported by the Sfno Prognostic pipeline
        """

        if dateobj < datetime(2021, 1, 1):
            raise InputTimeRangeError(
                f"Requested date time {dateobj}Z needs to be after 2021-01-01 for GFS data"
            )

        if len(set(variables)-set(["w10m", "u10m", "v10m", "t2m", "tp", "tcwv"])):
            carb.log_error(f"Invalid requested variables {variables}")
            raise InputVariableError(f"Invalid requested variable(s) {', '.join([VARIABLE_LABELS[var] for var in variables])} for Sfno Prognostic")


    @classmethod
    def execute(cls, site: str, variable: str, dateobj: datetime, num_timesteps: int = 1):
        """Execute Sfno Prognostic data pipeline

        Runs the Sfno Prognostic pipeline
        to fetch and process data for the specified variable and datetime.

        Parameters
        ----------
        site : str
            DFM site identifier for pipeline execution
        variable : str
            Variable to fetch (e.g., 'w10m', 'u10m', 'v10m', 't2m', 'tp', 'tcwv')
        dateobj : datetime
            Datetime object specifying when to fetch data from (2021-01-01 to present)
        num_timesteps : int, optional
            Number of timesteps to fetch (default: 1)

        Returns
        -------
        Future[Any]
            Future of the running coroutine the pipeline is executed in
        """
        # Input validation
        cls.input_validation([variable], dateobj)

        # Create single pipeline
        pipeline, input_params, places = cls._create_pipeline(
            variable, dateobj, num_timesteps=num_timesteps, site=site
        )


        callback = partial(cls.pipeline_callback, variable=variable, dateobj=dateobj, num_timesteps=num_timesteps)

        # Run DFM pipeline
        promise = async_engine.run_coroutine(run_pipeline(
                pipeline,
                input_params,
                places,
                callback
            )
        )

        return promise

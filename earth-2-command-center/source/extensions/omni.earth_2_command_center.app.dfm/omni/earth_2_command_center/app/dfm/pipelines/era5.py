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
import json
import carb
import omni.kit.async_engine as async_engine
from functools import partial
from datetime import datetime, timezone, timedelta
from typing import Any

# Import DFM API and client packages that can be used to build and run pipelines.

from dfm.api import Pipeline, Yield, PlaceParam, StopToken

from federation.api import TextureFile, TextureFileList

# Import adapters with error handling
try:
    from federation.fed.api.earth2 import LoadEcmwfEra5Data
except ImportError:
    carb.log_warning("ERA5 adapter is not available in the installed DFM client package")
    LoadEcmwfEra5Data = None
from federation.fed.api.earth2 import ConvertToUint8, RenderUint8ToImages, VariableNorm


from ..utils import create_dfm_image_feature, run_pipeline
from ..utils.constants import VARIABLE_CMAP, VARIABLE_LABELS, VARIABLE_RANGE, VARIABLE_UNIT
from ..utils.exceptions import InputVariableError, InputTimeRangeError

from ._base import PipelineBase

class ERA5Pipeline(PipelineBase):

    variable_map = {
        "u10m": "10m_u_component_of_wind",
        "v10m": "10m_v_component_of_wind",
        "t2m": "2m_temperature",
        "tp": "total_precipitation",
        "tcwv": "total_column_water_vapour"
    }

    @staticmethod
    def name():
        return "ECMWF ReAnalysis 5"

    @classmethod
    def _create_pipeline(
        cls, variable: str, date: datetime, site: str = "client1", num_timesteps: int = 1, step_size_h: int = 6,
        return_image_data: bool = True,
    ) -> tuple[Pipeline, list[dict[str, Any]], list[str]]:
        """
        Build a DFM pipeline for ERA5 reanalysis data processing.

        Creates a pipeline that fetches ECMWF ERA5 reanalysis data, applies
        normalization and scaling, and renders the data as JPEG textures
        for historical weather visualization. Uses variable mapping to convert
        between internal and ERA5 variable names.

        Parameters
        ----------
        variable : str
            Weather variable to process (e.g., 'w10m', 't2m', 'tp', etc.)
        date : datetime
            Starting datetime for data retrieval (1959-2021 range)
        site : str, optional
            DFM site identifier (default: "client1")
        num_timesteps : int, optional
            Number of timesteps to process (default: 1)
        step_size_h : int, optional
            Hours between timesteps, typically 6 for ERA5 data (default: 6)
        return_image_data : bool, optional
            Whether to return image data (default: False)

        Returns
        -------
        tuple[Pipeline, list[dict[str, Any]], list[str]]
            Pipeline object, input parameters, and yield place names
        """
        # Check for required adapters
        if LoadEcmwfEra5Data is None:
            import dfm
            raise ImportError(
                f"ERA5 adapter is not available in the installed DFM package (version {dfm.__version__}). "
                "To update the package, replace the wheel in deps/wheels and delete the _build folder "
                "then rebuild from scratch."
            )

        # Here we start building the pipeline object.
        # Please notice that we don't perform any data processing here,
        # This code only builds a description of the processing that will
        # happen inside DFM site.

        places = []
        with Pipeline() as pipeline:
            ecmwf_data = LoadEcmwfEra5Data(
                site=site,
                variables=PlaceParam(place="load_variables", multiuse=True),
                selection=PlaceParam(place="load_selection"),
            )
            for texture in ["diffuse", "alpha"]:
                if texture == "alpha" and variable == "w10m":
                    data_norm = VariableNorm(
                        site=site,
                        data=ecmwf_data,
                        variables=PlaceParam(place="load_variables", multiuse=True),
                        p=1,
                        output_name=PlaceParam(place=f"render_variable", multiuse=True),
                    )
                    # Scale values to UINT8 range
                    tex = ConvertToUint8(
                        site=site,
                        data=data_norm,
                        time_dimension="time",
                        xydims=["longitude", "latitude"],
                        min_value=1, # clip bottom to get more transparent
                        max_value=PlaceParam(place=f"max_value", multiuse=True),
                    )
                else:
                    # Scale values to UINT8 range
                    tex = ConvertToUint8(
                        site=site,
                        data=ecmwf_data,
                        time_dimension="time",
                        xydims=["longitude", "latitude"],
                        min_value=PlaceParam(place=f"min_value", multiuse=True),
                        max_value=PlaceParam(place=f"max_value", multiuse=True),
                    )

                render_uint8_to_images = RenderUint8ToImages(
                    site=site,
                    data=tex,
                    variable=PlaceParam(place=f"render_variable", multiuse=True),
                    xydims=["longitude", "latitude"],
                    time_dimension="time",
                    additional_meta_data=PlaceParam(place=f"extra_meta_data_{texture}"),
                    return_meta_data=True,
                    return_image_data=return_image_data,
                    format="jpeg",
                )
                place = f"yield_{texture}"
                places.append(place)
                Yield(value=render_uint8_to_images, place=place)

        # Prepare input parameters
        input_params = []

        # Handle wind components
        variables = ["u10m", "v10m"] if variable == "w10m" else [variable]
        current_time: datetime = date
        delta = timedelta(hours=step_size_h)

        for var in variables:
            for _ in range(num_timesteps):
                min_value = VARIABLE_RANGE[var][0]
                max_value = VARIABLE_RANGE[var][1]
                era5_variable = cls.variable_map[var]
                ip = {
                    "load_variables": [era5_variable],
                    "load_selection": json.dumps({"time": current_time.isoformat()}),
                    "min_value": min_value,
                    "max_value": max_value,
                    "render_variable": era5_variable,
                    "extra_meta_data_alpha": json.dumps(
                        {
                            "variable": var,
                            "texture": "alpha",
                        }
                    ),
                    "extra_meta_data_diffuse": json.dumps(
                        {
                            "variable": var,
                            "texture": "diffuse",
                        }
                    ),
                }
                carb.log_info(f"Adding input params: {ip}")
                input_params.append(ip)
                current_time += delta

        return pipeline, input_params, places

    @classmethod
    def pipeline_callback(cls,
                          response: Any,
                          variable: str,
                          dateobj: datetime) -> None:
        """
        Process ERA5 pipeline response and create DFM image features.

        Handles the results from the ERA5 pipeline execution, extracting texture
        files and creating image features for historical weather reanalysis visualization.

        Parameters
        ----------
        response : Any
            Pipeline response containing texture files or stop token
        variable : str
            Original requested weather variable name
        dateobj : datetime
            Original requested datetime for reanalysis data

        Returns
        -------
        None
        """

        carb.log_info(f"ERA5 Pipeline callback received response: {response}")
        if isinstance(response, StopToken):
            carb.log_info("ERA5 Pipeline is finished")
            return

        assert isinstance(response, TextureFileList)
        assert len(response.texture_files) == 1
        texture: TextureFile = response.texture_files[0]


        # Get the actual variable from metadata if it exists (for wind components)
        actual_variable = texture.metadata.get("variable", variable) if texture.metadata else variable
        variable_label = VARIABLE_LABELS[actual_variable] if actual_variable in VARIABLE_LABELS else actual_variable

        # Create meta data needed by the blueprint API
        meta_data = {
            "variable_label": variable_label,
            "source_label": "ERA5",
            "type_label": "analysis",
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

        name = f"ERA5 {actual_variable} {dateobj.isoformat()}"

        if texture.metadata.get("texture") == "diffuse":
            create_dfm_image_feature([texture.url], [], [timestamp], name, meta_data, cmap=VARIABLE_CMAP[actual_variable])
        else:
            create_dfm_image_feature([], [texture.url], [timestamp], name, meta_data, cmap=VARIABLE_CMAP[actual_variable])


    @classmethod
    def input_validation(cls, variables: list[str], dateobj: datetime) -> None:
        """Validate input parameters for ERA5 pipeline

        Validates that the requested variables and datetime are supported by the
        ERA5 reanalysis dataset and within the historical data range (1959-2021).

        Parameters
        ----------
        variables : list[str]
            List of variables to fetch (must be from: w10m, u10m, v10m, t2m, tp, tcwv)
        dateobj : datetime
            Datetime object to fetch (must be hourly intervals between 1959-2021)

        Raises
        ------
        InputTimeRangeError
            If datetime is outside valid range or not on hourly intervals
        InputVariableError
            If variables are not supported by ERA5
        """
        if not (dateobj - datetime(1900, 1, 1)).total_seconds() % 3600 == 0:
            raise InputTimeRangeError(
                f"Requested date time {dateobj}Z needs to be 1 hour interval for ERA5"
            )

        if dateobj > datetime(year=2021, month=12, day=31):
            raise InputTimeRangeError(f"Requested date time {dateobj} needs to be before December 31, 2021 for ERA5 data")

        if dateobj < datetime(year=1959, month=1, day=1):
            raise InputTimeRangeError(
                f"Requested date time {dateobj}Z needs to be after January 1st, 1959 (UTC) for ERA5 data"
            )

        if len(set(variables)-set(["w10m", "u10m", "v10m", "t2m", "tp", "tcwv"])):
            carb.log_error(f"Invalid requested variables {variables}")
            raise InputVariableError(f"Invalid requested variable(s) {', '.join([VARIABLE_LABELS[var] for var in variables])} for ERA5")

    @classmethod
    def execute(cls, site: str, variable: str, dateobj: datetime, num_timesteps: int = 1):
        """Execute ERA5 reanalysis data pipeline

        Runs the ECMWF ReAnalysis 5 (ERA5) pipeline to fetch and process
        historical reanalysis data for the specified variable and datetime.

        Parameters
        ----------
        site : str
            DFM site identifier for pipeline execution
        variable : str
            Variable to fetch (e.g., 'w10m', 'u10m', 'v10m', 't2m', 'tp', 'tcwv')
        dateobj : datetime
            Datetime object specifying when to fetch data from (1959-2021)
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
        pipeline, input_params, places = cls._create_pipeline(variable, dateobj, num_timesteps=num_timesteps, site=site)


        callback = partial(cls.pipeline_callback, variable=variable, dateobj=dateobj)

        # Run DFM pipeline
        promise = async_engine.run_coroutine(run_pipeline(
                pipeline,
                input_params,
                places,
                callback
            )
        )

        return promise

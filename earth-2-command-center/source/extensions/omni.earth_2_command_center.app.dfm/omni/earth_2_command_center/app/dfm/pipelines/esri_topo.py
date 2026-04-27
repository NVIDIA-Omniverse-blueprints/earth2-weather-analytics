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
import carb
import omni.kit.async_engine as async_engine
from functools import partial
from datetime import datetime, timezone
from typing import Any

# Import DFM API and client packages that can be used to build and run pipelines.

from dfm.api import Pipeline, Yield, PlaceParam, StopToken

from federation.api import TextureFile

# Import adapters with error handling
try:
    from federation.fed.api.earth2 import LoadEsriElevationData
except ImportError:
    carb.log_warning("ESRI adapter is not available in the installed DFM client package")
    LoadEsriElevationData = None


from ..utils import create_dfm_image_feature, run_pipeline
from ..utils.exceptions import InputVariableError

from ._base import PipelineBase

SUPPORTED_ESRI_PROCESSING_MODES = [ "none",
                                    "hillshade",
                                    "multi_directional_hillshade",
                                    "elevation_tinted_hillshade",
                                    "ellipsoidal_height",
                                    "slope_degrees_map",
                                    "aspect_map"
]

MAPPING_DEFAULTS =  {
    "input_min" : 0.00, "input_max" : 1.0,
    "output_min" : 0.0,"output_max" : 1.0,
    "output_gamma" : 1.0
}

# some magic remap settings per processing mode
ESRI_REMAP_SETTINGS = {
    "none": {"input_min" : 0.05},
    "hillshade": {"input_min" : 0.67},
    "multi_directional_hillshade": {"input_min" : 0.42, "output_gamma": 0.14},
    "elevation_tinted_hillshade": {"output_gamma": 0.30},
    "ellipsoidal_height": {"input_min" : 0.04},
    "slope_degrees_map": {"input_min" : 0.7, "output_gamma": 0.27},
    "aspect_map": {"output_gamma": 0.40},
}

class ESRITopoPipeline(PipelineBase):

    @staticmethod
    def name():
        return "ESRI Topology Map"

    @staticmethod
    def _create_pipeline(processing: str,
                         image_size: tuple[int, int] = (1000, 1000),
                         site: str = "homesite") -> tuple[Pipeline, list[dict[str, Any]], list[str]]:
        """
        Build a DFM pipeline for ESRI topographic elevation data processing.

        Creates a pipeline that fetches ESRI elevation data and applies various
        topographic processing modes (hillshade, slope, aspect, etc.) to generate
        terrain visualization textures as JPEG images.

        Parameters
        ----------
        processing : str
            Topographic processing mode to apply to elevation data
        image_size : tuple[int, int], optional
            Output image dimensions in pixels (width, height) (default: (1000, 1000))
        site : str, optional
            DFM site identifier (default: "homesite")

        Returns
        -------
        tuple[Pipeline, list[dict[str, Any]], list[str]]
            Pipeline object, input parameters (empty for ESRI), and yield place names
        """
        if LoadEsriElevationData is None:
            import dfm
            raise ImportError(
                f"ESRI adapter is not available in the installed DFM package (version {dfm.__version__}). "
                "To update the package, replace the wheel in deps/wheels and delete the '_build' folder "
                "then rebuild from scratch."
            )

        # Here we start building the pipeline object.
        # Please notice that we don't perform any data processing here,
        # This code only builds a description of the processing that will
        # happen inside DFM site.
        # FunctionCall.set_allow_outside_block()
        with Pipeline() as pipeline:
            texture = LoadEsriElevationData(
                site=site,
                lat_minmax=[-85, 85],
                lon_minmax=[-180, 180],
                wkid=4326,
                processing=processing,
                output="texture",
                texture_format="jpeg",
                image_size=image_size,
                return_meta_data=True,
                return_image_data=False,
            )
            Yield(value=texture)

        # Return the pipeline object.
        return pipeline, [], ["yield"]

    @classmethod
    def pipeline_callback(cls,
                          response: StopToken | TextureFile,
                          processing: str,
                          image_size: tuple[int, int]) -> None:
        """
        Process ESRI topographic pipeline response and create DFM image features.

        Handles the results from the ESRI elevation pipeline execution, extracting
        texture files and creating image features for topographic terrain visualization.
        Applies processing-specific remapping and metadata configuration.

        Parameters
        ----------
        response : StopToken | TextureFile
            Pipeline response containing texture file or stop token
        processing : str
            Topographic processing mode that was applied to elevation data
        image_size : tuple[int, int]
            Requested image dimensions used for processing

        Returns
        -------
        None
        """
        if isinstance(response, StopToken):
            carb.log_info("ESRI Pipeline is finished")
            return

        assert isinstance(response, TextureFile)
        texture: TextureFile = response

        settings = carb.settings.get_settings()
        tokens = carb.tokens.get_tokens_interface()
        world_alpha_mask = tokens.resolve(settings.get(f"/exts/omni.earth_2_command_center.app.dfm/world_alpha_mask"))

        remapping = MAPPING_DEFAULTS | ESRI_REMAP_SETTINGS.get(processing, {})

        # Create meta data needed by the blueprint API
        meta_data = {
            "variable_label": processing.replace("_", " ").title() + " Topography",
            "esri_topo_processing": processing,
            "esri_topo_tex_req_size": image_size,
            "esri_topo_tex_out_size": (texture.metadata['width'], texture.metadata['height']),
            "source_label": "ESRI", # Linked to blueprint api in state.py
            "type_label": "static",
            "remapping": remapping
        }

        timestamp = datetime.strptime(texture.timestamp, "%Y-%m-%dT%H:%M")
        if not timestamp.tzinfo:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if texture.metadata:
           meta_data.update(texture.metadata)

        rgb_images = [texture.url]
        alpha_images = [world_alpha_mask]

        name = f"ESRITopography_{processing}"
        create_dfm_image_feature(image_urls=rgb_images,
                                 alpha_image_urls=alpha_images,
                                 image_timestamps=[timestamp],
                                 feature_name=name,
                                 meta_data=meta_data,
                                 rescale_timeline=False,
                                 is_full_globe=False,
                                 adjust_offsets=True)


    @classmethod
    def input_validation(cls, processing: str) -> None:
        """Validate input parameters for ESRI topographic pipeline

        Validates that the requested processing mode is supported by the
        ESRI elevation data service.

        Parameters
        ----------
        processing : str
            Processing mode for topographic data (must be one of: none, hillshade,
            multi_directional_hillshade, elevation_tinted_hillshade, ellipsoidal_height,
            slope_degrees_map, aspect_map)

        Raises
        ------
        InputVariableError
            If processing mode is not supported by ESRI topographic service
        """

        if processing not in set(SUPPORTED_ESRI_PROCESSING_MODES):
            raise InputVariableError(f"Unknown processing mode {processing} for ESRI topographic map")

    @classmethod
    def execute(cls, site: str, processing: str):
        """Execute ESRI topographic mapping pipeline

        Runs the ESRI Topology Map pipeline to fetch and process elevation data
        with various topographic processing modes for terrain visualization.

        Parameters
        ----------
        site : str
            DFM site identifier for pipeline execution
        processing : str
            Processing mode for topographic data (e.g., 'hillshade', 'elevation_tinted_hillshade',
            'multi_directional_hillshade', 'slope_degrees_map', 'aspect_map', etc.)

        Returns
        -------
        Future[Any]
            Future of the running coroutine the pipeline is executed in
        """
        image_size = [4500, 4500]

        # Create a list of variables to fetch
        # Do one variable at a time because it makes the pipelines easier to manage
        cls.input_validation(processing)
        pipeline, input_params, places = cls._create_pipeline(processing=processing, image_size=image_size, site=site)

        # Returns a asyncio task
        callback = partial(cls.pipeline_callback, processing=processing, image_size=image_size)

        promise = async_engine.run_coroutine(run_pipeline(pipeline, input_params, places, callback))
        return promise

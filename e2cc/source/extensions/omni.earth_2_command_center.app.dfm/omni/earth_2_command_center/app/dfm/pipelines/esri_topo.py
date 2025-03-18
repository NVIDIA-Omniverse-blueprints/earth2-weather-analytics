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
from datetime import datetime, timezone
from typing import Tuple, Dict, Any, TypeVar

# Import DFM API and client packages that can be used to build and run pipelines.
from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalAllDone, TextureFile
try:
    from dfm.api.esri import LoadElevationData
except ImportError:
    LoadElevationData = None
from dfm.api.response import ValueResponse

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

MAPPING_DEFAULTS =  {  "input_min" : 0.00, "input_max" : 1.0,
                    "output_min" : 0.0,"output_max" : 1.0,
                    "output_gamma" : 1.0}

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
                         image_size: Tuple[int, int] = [1000, 1000],
                         esri_provider: str = "esri") -> Process:
        """
        A helper function that uses provided settings to build a pipeline.
        """
        if LoadElevationData is None:
            import dfm
            raise ImportError(
                f"ESRI adapter is not available in the installed DFM package (version {dfm.__version__}). "
                "To update the package, replace the wheel in deps/wheels and delete the '_build' folder "
                "then rebuild from scratch."
            )
        force_texture_compute = False  # Controls texture cache.

        # Here we start building the pipeline object.
        # Please notice that we don't perform any data processing here,
        # This code only builds a description of the processing that will
        # happen inside DFM site.
        # FunctionCall.set_allow_outside_block()
        with Process() as pipeline:
            texture_rgb = LoadElevationData(
                provider=esri_provider,
                node_id=well_known_id('elevation'),
                lat_minmax=[-85, 85],
                lon_minmax=[-180, 180],
                wkid=4326,
                processing=processing,
                image_size=image_size,
                output="texture",
                texture_format="jpeg",
                is_output=True,
                force_compute=force_texture_compute,
                return_meta_data=True,
                return_image_data=False
            )

            SignalAllDone(node_id=well_known_id('all_done'), after=[texture_rgb], message='done')

        # Return the pipeline object.
        carb.log_warn(pipeline)
        return pipeline

    @classmethod
    def pipeline_callback(cls, node_id: UUID,
                          response: ValueResponse,
                          processing: str,
                          image_size: Tuple[int, int]) -> None:
        """Pipeline call back after successful response

        Parameters
        ----------
        response : ValueResponse
            DFM Response object
        """
        if response.value == 'done':
            carb.log_info("ESRI Pipeline is finished")
            return

        api_class = response.value.get('api_class', 'unknown') if isinstance(response.value, dict) else 'unknown'
        if api_class == 'dfm.api.dfm.TextureFile':
            texture: TextureFile = TextureFile.model_validate(response.value)
        else:
            raise ValueError("expected TextureFile class here")

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
        """Offline check input requests

        Check the DFM code, for look for advice decorators,

        Parameters
        ----------
        processing : str
           processing type applied to the topology data

        Raises
        ------
        ValueError
            If invalid inputs
        """

        if processing not in set(SUPPORTED_ESRI_PROCESSING_MODES):
            raise InputVariableError(f"Unknown processing mode {processing} for ESRI topographic map")

    @classmethod
    def execute(cls, processing: str, dfm_url: str = "http://localhost:8080"):
        """Sync execute script for FCN pipeline

        Parameters
        ----------
        processing : str
            processing type applied to the topology data
        dfm_url : str, optional
            URL of running DFM server, by default "http://localhost:8080"

        Returns
        -------
        Future[Any]
            future of the running coroutine the pipeline is executed in
        """
        image_size = [4500, 4500]

        # Create a list of variables to fetch
        # Do one variable at a time because it makes the pipelines easier to manage
        cls.input_validation(processing)
        pipeline = cls._create_pipeline(processing=processing, image_size=image_size)
        # Returns a asyncio task
        callback = partial(cls.pipeline_callback,
                           processing=processing,
                           image_size=image_size)
        promise = async_engine.run_coroutine(run_pipeline(pipeline, callback, dfm_url))

        return promise

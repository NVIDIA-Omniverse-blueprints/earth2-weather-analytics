# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""
This module implements the FourCastNet pipeline for the Earth2 Blueprint.
It handles loading data, running the FourCastNet model, and processing the outputs.
"""

import argparse
import asyncio
import logging
import base64

from enum import Enum, auto
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List

from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalClient
from dfm.api.data_loader import LoadEra5ModelData
from dfm.api.nwp import InvokeNimNwpDnn
from dfm.api.xarray import ConvertToUint8, RenderUint8ToImages, VariableNorm
from dfm.api.response import ValueResponse, StatusResponse, HeartbeatResponse
from dfm.client import AsyncClient

# Configure logging
logging.basicConfig(level=logging.INFO)

# Constants for variable configurations
VARIABLE_RANGE = {
    "t2m": (250, 320),
    "u10m": (-30, 30),
    "v10m": (-30, 30),
    "w10m": (0, 30),
    "tp": (0, 0.1),
    "tcwv": (0, 70),
}


class PipelineVariant(Enum):
    """Available pipeline variants"""

    FOURCASTNET = auto()


@dataclass
class PipelineSettings:
    """Settings for configuring the FourCastNet pipeline"""

    date: datetime
    variables: List[str]
    loader_provider: str = "gfs"
    nim_provider: str = "fourcastnet"
    num_samples: int = 1
    force_compute: bool = False


class FourCastNetPipeline:
    """Pipeline implementation for FourCastNet"""

    @staticmethod
    def create_pipeline(settings: PipelineSettings) -> Process:
        """Creates a FourCastNet pipeline based on provided settings"""

        # Handle wind components
        variables = (
            ["u10m", "v10m"] if "w10m" in settings.variables else settings.variables
        )

        with Process() as pipeline:
            wait_list = []

            # Load data
            data = LoadEra5ModelData(
                provider=settings.loader_provider,
                variables=["*"],  # DNN needs all variables
                selection={"time": settings.date.isoformat()},
                force_compute=settings.force_compute,
            )

            # Run FourCastNet model
            nim = InvokeNimNwpDnn(
                provider=settings.nim_provider,
                data=data,
                variables=variables,
                samples=settings.num_samples,
                force_compute=settings.force_compute,
            )

            # Process each variable
            for var in variables:
                min_value = VARIABLE_RANGE[var][0]
                max_value = VARIABLE_RANGE[var][1]

                for texture in ["diffuse", "alpha"]:
                    if texture == "alpha" and "w10m" in settings.variables:
                        # Normalize wind components
                        data_norm = VariableNorm(
                            data=nim, variables=[var], p=1, output_name=var
                        )
                        tex = ConvertToUint8(
                            data=data_norm,
                            time_dimension="time",
                            xydims=("lon", "lat"),
                            min=1,
                            max=max_value,
                        )
                    else:
                        tex = ConvertToUint8(
                            data=nim,
                            time_dimension="time",
                            xydims=("lon", "lat"),
                            min=min_value,
                            max=max_value,
                        )

                    # Render images
                    render = RenderUint8ToImages(
                        provider="local_earth2_textures",
                        is_output=True,
                        data=tex,
                        time_dimension="time",
                        xydims=("lon", "lat"),
                        variable=var,
                        force_compute=settings.force_compute,
                        return_meta_data=True,
                        return_image_data=True,
                        additional_meta_data={"variable": var, "texture": texture},
                    )
                    wait_list.append(render)

            # Signal completion
            SignalClient(
                node_id=well_known_id("all_done"),
                after=wait_list[-1],
                message="done",
            )

        return pipeline


async def run_pipeline(
    log: logging.Logger, dfm_url: str, settings: PipelineSettings, verbose: bool = False
) -> None:
    """Runs the FourCastNet pipeline and handles responses"""

    pipeline = FourCastNetPipeline.create_pipeline(settings)

    async with AsyncClient(
        url=dfm_url, logger=logging.getLogger("earth2.client"), retries=5
    ) as client:
        version = await client.version()
        log.info("Using DFM %s site %s", version, dfm_url)

        request_id = await client.process(pipeline)
        log.info("DFM accepted request and returned request ID %s", request_id)

        async for response in client.responses(
            request_id=request_id,
            stop_node_ids=well_known_id("all_done"),
            return_statuses=True,
        ):
            if not response:
                await asyncio.sleep(0.5)
                continue

            client.raise_on_error(response)

            if isinstance(response.body, ValueResponse):
                if response.node_id == well_known_id("image"):
                    # It's an image, so we get image data and save it to a file.
                    file_path = Path(response.body.value["url"]).name
                    image_data = base64.b64decode(
                        response.body.value["base64_image_data"]
                    )
                    with open(file_path, "wb") as file:
                        file.write(image_data)
                    log.info("Received image saved to %s", file_path)
                else:
                    log.info("Received response: %s", response.body.value)
            elif isinstance(response.body, StatusResponse) and verbose:
                log.info("Received status update: %s", response.body.message)
            elif isinstance(response.body, HeartbeatResponse) and verbose:
                log.info("Received heartbeat")

        log.info("Pipeline execution completed.")


if __name__ == "__main__":
    log = logging.getLogger("earth2")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s", "--site", default="http://localhost:8080", type=str, help="DFM site URL"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--variable", default="t2m", type=str, help="Variable to forecast"
    )
    parser.add_argument(
        "--date", type=str, help="Date in format MM/DD/YY HH:MM:SS", required=True
    )

    args = parser.parse_args()

    settings = PipelineSettings(
        date=datetime.strptime(args.date, "%m/%d/%y %H:%M:%S"),
        variables=[args.variable],
    )

    asyncio.run(run_pipeline(log, args.site, settings, args.verbose))

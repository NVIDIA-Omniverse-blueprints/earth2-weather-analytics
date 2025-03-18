# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# -*- coding: utf-8 -*-

"""
This example demonstrates how to build an execution pipeline for the Earth2 Blueprint,
and use the client library to run the pipeline. It also shows how to handle received responses.
"""

# Import basic Python packages.
import argparse
import asyncio
import base64
import logging

from enum import Enum, auto
from pathlib import Path


from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalClient
from dfm.api.data_loader import LoadHrrrModelData
from dfm.api.xarray import ConvertToUint8, RenderUint8ToImages
from dfm.api.response import ValueResponse, StatusResponse, HeartbeatResponse

from dfm.client import AsyncClient

# Configure simple logging facility
logging.basicConfig(level=logging.INFO)


class PipelineVariant(Enum):
    """
    This example provides multiple pipelines that can be built and executed.
    """

    EARTH2_HRRR = auto()


class PipelineFactory:
    """
    A convenience class that helps building Pipeline objects
    that can be submitted to the DFM for execution.
    """

    @classmethod
    def get(cls, variant: str | PipelineVariant):
        """
        Translates pipeline variant to actual pipeline object
        using factory functions.
        """
        if isinstance(variant, str):
            variant = PipelineVariant[variant.upper()]
        return getattr(PipelineFactory, variant.name.lower())()

    def earth2_hrrr():
        """
        Returns HRRR pipeline.
        """
        force_loader_compute = True  # Disable loader cache.
        force_texture_compute = True  # Disable texture cache.

        with Process() as pipeline:
            # Load HRRR data from configured provider.
            data = LoadHrrrModelData(
                provider="hrrr",
                variables=["t2m"],
                time="2022-06-27",
                step=0,
                force_compute=force_loader_compute,
            )
            min_value = 200.0
            max_value = 400.0
            xydims = ("longitude", "latitude")
            # Scale values to UINT8 range.
            tex = ConvertToUint8(
                data=data,
                time_dimension="time",
                xydims=xydims,
                min=min_value,
                max=max_value,
                force_compute=force_texture_compute,
            )
            # Convert the scaled data to a grayscale image.
            render_images = RenderUint8ToImages(
                provider="local_earth2_textures",
                node_id=well_known_id("image"),
                is_output=True,
                data=tex,
                time_dimension="time",
                xydims=xydims,
                force_compute=force_texture_compute,
                return_meta_data=True,
                return_image_data=True,
            )
            # Send 'all_done' signal to the client when the processing is done.
            SignalClient(
                node_id=well_known_id("all_done"), after=render_images, message="done"
            )
        # Return the pipeline object.
        return pipeline


async def main(
    log: logging.Logger,
    dfm_url: str,
    pipeline_variant: str | PipelineVariant,
    verbose: bool = False,
):
    """
    This function demonstrates how to run a pipeline and process received responses.
    """
    # PipelineFactory returns a Python object describing the processing pipeline.
    pipeline = PipelineFactory.get(pipeline_variant)

    # We're using an asynchronous client for communication with the node
    async with AsyncClient(
        url=dfm_url, logger=logging.getLogger("earth2.client"), retries=5
    ) as client:
        # Obtain basic version information first to check connectivity.
        version = await client.version()
        log.info("Using DFM %s site %s", version, dfm_url)
        # Submit our pipeline for execution
        request_id = await client.process(pipeline)
        log.info("DFM accepted request and returned request ID %s", request_id)
        # Client returns an empty value, there's no response available,
        # but we should keep polling until
        #   a) timeout happens
        #   b) a new response is available
        # We tell the client to finish the loop when 'all_done' signal is received.
        async for response in client.responses(
            request_id=request_id,
            stop_node_ids=well_known_id("all_done"),
            return_statuses=True,
        ):
            if not response:
                # No responses available, back off a little
                await asyncio.sleep(0.5)
                continue
            # Raise an exception if we receive error response
            client.raise_on_error(response)
            # Now we know that the response is not indicating an error, so we need to check
            # what exactly we have received. We asked the client to return all responses,
            # including status updates and heart beats.
            if isinstance(response.body, ValueResponse):
                # We received a value.
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
                    # Not an image - just display the received value.
                    log.info("Received response: %s", response.body.value)
            elif isinstance(response.body, StatusResponse) and verbose:
                log.info("Received status update: %s", response.body.message)
            elif isinstance(response.body, HeartbeatResponse) and verbose:
                log.info("Received heartbeat")
        # Client received 'all_done' signal and finished iterating.
        log.info("Done.")


if __name__ == "__main__":
    log = logging.getLogger("earth2")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--site",
        default="http://localhost:8080",
        type=str,
        nargs="?",
        help="DFM site URL, defaults to local port-forwarded service",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Be more verbose: show status messages",
    )
    parser.add_argument(
        "-p",
        "--pipeline",
        default="earth2_hrrr",
        type=str,
        nargs="?",
        help="Pipeline to execute",
    )
    args = parser.parse_args()

    try:
        pipeline_variant = PipelineVariant[args.pipeline.upper()]
    except KeyError:
        log.error("Unknown pipeline variant: %s", args.pipeline)
    else:
        asyncio.run(main(log, args.site, pipeline_variant, args.verbose))

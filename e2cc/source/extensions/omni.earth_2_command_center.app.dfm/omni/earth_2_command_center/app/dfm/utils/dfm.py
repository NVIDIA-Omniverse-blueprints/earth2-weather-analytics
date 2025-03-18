# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import asyncio
import logging
import carb
from typing import Callable

from dfm.client import AsyncClient
from dfm.api import Process, well_known_id
from dfm.api.response import Response, ValueResponse, StatusResponse, HeartbeatResponse


async def run_pipeline(
    pipeline: Process,
    callback: Callable[[Response], None],
    dfm_url: str = "http://localhost:8080",
):
    """Async util method for running a pipeline process

    Parameters
    ----------
    pipeline : Process
        DFM pipeline to run
    callback : Callable[[ValueResponse],None]
        Callback function that processes a successful value request, specific to each pipeline
    dfm_url : _type_, optional
        DFM server URL, by default "http://localhost:8080"
    """
    carb.log_info("Running pipeline")
    try:
        # TODO: Add large timeout catch here... need to confirm with DFM devs
        # basically even if
        # TODO: Figure out how to give carb logger instead
        async with AsyncClient(
            url=dfm_url, logger=logging.getLogger("earth2.client"), retries=1
        ) as client:
            # Obtain basic version information first to check connectivity.
            version = await client.version()
            carb.log_info(f"DFM instance found running version {version}")
            # Submit our pipeline for execution
            request_id = await client.process(pipeline)

            # Client returns an empty value, there's no response available,
            # but we should keep polling until
            #   a) timeout happens
            #   b) a new response is available
            # We tell the client to finish the loop when 'all_done' signal is received.
            async def run_loop():
                async for response in client.responses(
                    request_id=request_id,
                    stop_node_ids=well_known_id("all_done"),
                    return_statuses=True,
                ):
                    # No response from DFM
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
                        callback(response.node_id, response.body)
                    elif isinstance(response.body, StatusResponse):
                        pass
                    elif isinstance(response.body, HeartbeatResponse):
                        pass

            # Await the loop so we can catch any errors
            await run_loop()
            # Client received 'all_done' signal and finished iterating.
            carb.log_info("DFM pipeline successfully ran!")

    except Exception as e:
        # Catch any error in the piptline execution here
        carb.log_error(e)
        carb.log_error(e.with_traceback())
        raise e

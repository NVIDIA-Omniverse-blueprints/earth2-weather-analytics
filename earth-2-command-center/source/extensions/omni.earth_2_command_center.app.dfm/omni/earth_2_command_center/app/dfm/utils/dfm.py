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
import base64
import os
import tempfile
import threading

from pathlib import Path
from queue import Queue, Empty
from typing import Callable, Any

from pydantic import ValidationError

import carb
import omni.kit.async_engine as async_engine

from nv_dfm_core.api import StopToken, ErrorToken, Pipeline
#from dfm.exec import Frame, TokenPackage
#from dfm.targets.flare import FlareOptions
#from dfm.session import Session
#
#from federation.api import TextureFile, TextureFileList
#
#def get_target() -> str:
#    """Get the DFM target environment from settings.
#
#    Returns:
#        str: The target environment ('local' or 'flare')
#
#    Raises:
#        ValueError: If the target is not 'local' or 'flare'
#    """
#    settings = carb.settings.get_settings()
#    target = settings.get("/exts/omni.earth_2_command_center.app.dfm/session/target")
#    if target not in ["local", "flare"]:
#        error_message = f"Invalid DFM target: {target}"
#        carb.log_error(error_message)
#        raise ValueError(error_message)
#    return target
#
#def get_site() -> str:
#    """Get the DFM site configuration for the current target.
#
#    Returns:
#        str: The site configuration string for the current target
#
#    Raises:
#        ValueError: If no site is configured for the current target
#    """
#    target = get_target()
#    settings = carb.settings.get_settings()
#    site = settings.get(f"/exts/omni.earth_2_command_center.app.dfm/session/site/{target}")
#    if site is None:
#        error_message = f"No DFM site found for target: {target}"
#        carb.log_error(error_message)
#        raise ValueError(error_message)
#    return site
#
#def iteration_timeout() -> int:
#    """Get the timeout duration for a single pipeline iteration.
#
#    Returns:
#        int: Timeout in seconds (default: 900 seconds / 15 minutes)
#    """
#    settings = carb.settings.get_settings()
#    timeout = settings.get_as_int("/exts/omni.earth_2_command_center.app.dfm/timeouts/iteration")
#    # Kit settings will return 0 as default if path does not exist...
#    if timeout == 0:
#        timeout = 900
#    return timeout
#
#
#def job_completion_timeout() -> int:
#    """Get the timeout duration for job completion after all iterations are done.
#
#    Returns:
#        int: Timeout in seconds (default: 120 seconds / 2 minutes)
#    """
#    settings = carb.settings.get_settings()
#    timeout = settings.get_as_int("/exts/omni.earth_2_command_center.app.dfm/timeouts/job_completion")
#    # Default: 2 minutes, since we wait only when we already know all iterations are done
#    # Kit settings will return 0 as default if path does not exist...
#    if timeout == 0:
#        timeout = 120
#    return timeout
#
#
#def flare_task_completion_timeout() -> int:
#    """Get the timeout duration for flare task completion.
#
#    Returns:
#        int: Timeout in seconds (default: 600 seconds / 10 minutes)
#    """
#    settings = carb.settings.get_settings()
#    timeout = settings.get_as_int("/exts/omni.earth_2_command_center.app.dfm/timeouts/flare_task_completion")
#    # Kit settings will return 0 as default if path does not exist...
#    if timeout == 0:
#        timeout = 600
#    return timeout
#
#def _get_session(target: str) -> Session:
#    """Create and configure a DFM session based on current settings.
#
#    Configures session parameters differently based on target:
#    - 'local': Uses minimal configuration
#    - 'flare': Requires user, workspace, and admin package settings
#
#    Returns:
#        Session: Connected DFM session ready for use
#    """
#    settings = carb.settings.get_settings()
#
#    session_info = f"DFM session settings: target: {target}"
#
#    if target == "flare":
#        user = settings.get("/exts/omni.earth_2_command_center.app.dfm/session/user")
#        flare_workspace = settings.get("/exts/omni.earth_2_command_center.app.dfm/session/flare_workspace")
#        job_workspace = settings.get("/exts/omni.earth_2_command_center.app.dfm/session/job_workspace")
#        admin_package = settings.get("/exts/omni.earth_2_command_center.app.dfm/session/admin_package")
#
#        def check_path(path: str) -> Path:
#            path = Path(path)
#            if not path.exists():
#                raise FileNotFoundError(f"Path does not exist: {path}")
#            return path
#
#        flare_workspace = check_path(flare_workspace)
#        job_workspace = check_path(job_workspace)
#        admin_package = check_path(admin_package)
#
#        session_info += f" user: {user} flare_workspace: {flare_workspace} job_workspace: {job_workspace} admin_package: {admin_package}"
#    elif target == "local":
#        pass # Maybe we add some local session info here later
#    else:
#        raise ValueError(f"Invalid target: {target}")
#
#    carb.log_info(session_info)
#
#    # Build session parameters based on target type
#    # Local target needs minimal config, flare target needs full workspace setup
#    session_params = {
#        "target": target,
#        "federation_name": "federation",
#        "homesite": "homesite",
#    } | ({} if target == "local" else {
#        "user": user,
#        "flare_workspace": flare_workspace,
#        "job_workspace": job_workspace,
#        "admin_package": admin_package,
#    })
#
#    session = Session(**session_params)
#    session.connect(debug=True)
#
#    return session
#
#def _drop_file_prefixes(data: TextureFile) -> None:
#    """Remove 'file://' prefixes from texture file URLs.
#
#    Args:
#        data: TextureFile object to modify in-place
#
#    Note:
#        This is needed because Dynamic Texture can't handle UPaths with file:// prefixes
#    """
#    # TODO: double check that Dynamic Texture can't handle UPaths
#    if data.url:
#        data.url = data.url.replace("file://", "")
#    if data.metadata_url:
#        data.metadata_url = data.metadata_url.replace("file://", "")
#
#def process_texture(data: TextureFile) -> None:
#    """Process texture file data by handling URLs or base64 image data.
#
#    For URL-based textures, removes file:// prefixes.
#    For base64-encoded textures, decodes and saves to temporary JPEG file.
#
#    Args:
#        data: TextureFile object to process in-place
#    """
#    if data.url or data.metadata_url:
#        _drop_file_prefixes(data)
#    if data.base64_image_data:
#        # Save base64-encoded image data to a temp jpeg file with unique name
#        # Note: We don't delete the file as it may be needed later by the texture system
#        temp_dir = tempfile.gettempdir()
#        file_descriptor, temp_file_path = tempfile.mkstemp(suffix=".jpeg", prefix="dfm_img_", dir=temp_dir)
#        os.close(file_descriptor)  # Close descriptor so we can write using normal file I/O
#
#        # Decode base64 data and write to temporary file
#        with open(temp_file_path, "wb") as f:
#            f.write(base64.b64decode(data.base64_image_data))
#
#        # Update the texture data to point to the temporary file
#        data.url = temp_file_path
#
async def _update_task(req_queue: Queue, resp_queue: Queue, callback: Callable[Any, None]) -> None:
    """Async task that processes pipeline data updates in the main thread.

    This task runs in the main thread to handle USD updates, since only the main
    thread can safely update USD. It receives data from the pipeline thread via
    the request queue and calls the user callback.

    Args:
        req_queue: Queue to receive data from pipeline thread
        resp_queue: Queue to send completion signals back to pipeline thread
        callback: User callback function to process the data
    """
    sleep_counter: int = 0
    while True:
        # Get the data from the queue
        try:
            data = req_queue.get_nowait()
        except Empty:
            # No data available, wait a bit before checking again
            if sleep_counter % 200 == 0:
                carb.log_info(f"Update task waiting for data")
            await asyncio.sleep(0.05)
            sleep_counter += 1
            continue

        sleep_counter = 0

        if isinstance(data, str) and data == "stop":
            carb.log_info(f"Update task received stop signal")
            return

        # Call the user's callback to process the data (must be in main thread for USD)
        callback(data)

        # Signal completion back to the pipeline thread
        resp_queue.put("done")


async def run_pipeline(
    pipeline: Pipeline,
    input_params: list[dict[str, Any]],
    places: list[str],
    callback: Callable[Any, None] | None,
) -> asyncio.Future:
    """Run a DFM pipeline asynchronously with proper thread coordination.

    Sets up communication between the main thread (for USD updates) and
    worker thread (for DFM pipeline execution). The pipeline runs through
    multiple iterations with the provided input parameters.

    Args:
        pipeline: DFM pipeline to execute
        input_params: List of parameter dictionaries, one per iteration
        places: List of place names to register callbacks for
        callback: User callback function to process pipeline outputs

    Returns:
        asyncio.Future: Future that completes when pipeline execution finishes
    """
    # Start the update task first. We need an update task to be running inside the main thread,
    # because only the main thread can update USD and we need to make updates from user callbacks.
    # Then we will start the pipeline thread. DFM session is synchronous, so we need to run it in a thread.

    # Communication queues between the pipeline thread and the update task.
    req_queue = Queue()
    resp_queue = Queue()

    # Start the update task. It will call the caller's callback when it receives a new data.
    task_promise = async_engine.run_coroutine(_update_task(req_queue, resp_queue, callback))

    # TODO: dummy
    def dummy():
        return

    # Start the pipeline thread
    thread_promise = async_engine.run_coroutine(
        asyncio.to_thread(dummy))
    #thread_promise = async_engine.run_coroutine(
    #    asyncio.to_thread(
    #        run_pipeline_thread_func,
    #        req_queue,
    #        resp_queue,
    #        pipeline,
    #        input_params,
    #        places,
    #    )
    #)

    promise = asyncio.gather(task_promise, thread_promise)
    return promise


#def run_pipeline_thread_func(
#    req_queue: Queue,
#    resp_queue: Queue,
#    pipeline: Pipeline,
#    input_params: list[dict[str, Any]],
#    places: list[str],
#) -> None:
#    """Execute DFM pipeline in a worker thread with proper error handling.
#
#    This function runs the actual DFM pipeline execution in a separate thread
#    to avoid blocking the main thread. It handles multiple iterations, error
#    conditions, and coordinates with the main thread via queues.
#
#    Args:
#        req_queue: Queue to send data to the main thread update task
#        resp_queue: Queue to receive completion signals from update task
#        pipeline: DFM pipeline to execute
#        input_params: List of parameter dictionaries for each iteration
#        places: List of place names to register yield callbacks for
#
#    Raises:
#        Exception: Re-raises any exception that occurs during pipeline execution
#    """
#    target = get_target()
#
#    try:
#        session = _get_session(target)
#    except Exception as e:
#        carb.log_error(f"Failed to get session: {e}")
#        raise e
#
#    def _trigger_update(data: Any):
#        """Send data to main thread and wait for processing completion."""
#        # Let the update task know we have something new to process.
#        req_queue.put(data)
#        # Wait for the response from the update task thread
#        signal: str = resp_queue.get()
#        assert signal == "done"
#
#    try:
#        # Condition variable to coordinate pipeline iteration timing
#        pipeline_ready = threading.Condition()
#
#        # Flag to check if an error has been received from DFM
#        error_present = False
#
#        def yield_callback(
#            _from_site: str,
#            _node: int | str | None,
#            _frame: Frame,
#            target_place: str,
#            data: Any,
#        ):
#            """Handle data yielded from pipeline places (e.g., texture outputs)."""
#            carb.log_info(
#                f"DFM callback: got message {data} from {target_place}"
#            )
#            # Check if we got an error token from DFM
#            try:
#                token = ErrorToken.model_validate(data)
#                # Let the executing loop know something went wrong
#                nonlocal error_present
#                error_present = True
#                for error in token.errors:
#                    carb.log_error(f"DFM callback received error: {error}")
#                # This pipeline is not going anywhere so let the executing loop know it should stop
#                with pipeline_ready:
#                    pipeline_ready.notify_all()
#                return
#            except ValidationError:
#                # Not an error token, continue processing
#                pass
#
#            # Process texture data (handle file URLs or base64 data)
#            if isinstance(data, TextureFile):
#                process_texture(data)
#            elif isinstance(data, TextureFileList):
#                for texture in data.texture_files:
#                    process_texture(texture)
#
#            # Trigger the update task
#            _trigger_update(data)
#
#        def default_callback(
#            _from_site: str,
#            _node: int | str | None,
#            frame: Frame,
#            _target_place: str,
#            data: Any,
#        ):
#            """Handle pipeline control frames (stop tokens, etc.)."""
#            # Check if it's a stop token indicating pipeline completion
#            try:
#                token = StopToken.model_validate(data)
#                if frame.is_stop_frame():
#                    carb.log_info("Received overall pipeline stop frame")
#                    # Trigger the update task for the stop token
#                    _trigger_update(token)
#                with pipeline_ready:
#                    pipeline_ready.notify_all()
#            except ValidationError:
#                # Not a stop token - log unexpected data
#                carb.log_warn(f"DFM callback received unexpected frame: {frame}, data: {data}")
#
#        # Set up callbacks for each place that yields data
#        callbacks = {place: yield_callback for place in places}
#
#        # Prepare the pipeline for execution
#        restrict_to_sites = "homesite" if target == "local" else None
#        prepared = session.prepare(pipeline, restrict_to_sites=restrict_to_sites)
#        # Ensure we have at least one iteration with empty params
#        input_params = [{}] if not input_params else input_params
#        iterations = len(input_params)
#        options = FlareOptions(
#            task_timeout_s=flare_task_completion_timeout(),
#        ) if target == "flare" else None
#
#        def wait_for_pipeline_ready():
#            """Wait for pipeline iteration to complete or timeout."""
#            with pipeline_ready:
#                pipeline_ready.wait(timeout=iteration_timeout())
#
#        # Execute pipeline iterations
#        for iteration in range(iterations):
#            if iteration == 0:
#                # Start the pipeline on first iteration (never use autostop)
#                job = session.execute(
#                    prepared,
#                    input_params=input_params[iteration],
#                    default_callback=default_callback,
#                    place_callbacks=callbacks,
#                    autostop=False,
#                    options=options,
#                )
#                carb.log_info(f"DFM job started: {job}")
#            else:
#                # Send new parameters for subsequent iterations
#                carb.log_info(f"Sending input params {input_params[iteration]} to DFM job")
#                job.send_input_params(input_params[iteration])
#
#            # Wait for this iteration to complete
#            wait_for_pipeline_ready()
#            if error_present:
#                # If an error has been received, bail out of pipeline execution
#                break
#
#        # Signal pipeline to stop after all iterations
#        carb.log_info(f"Sending stop frame to DFM job")
#        job.send_stop_frame()
#        wait_for_pipeline_ready()
#
#        # Wait for the entire job to complete
#        carb.log_info(f"Waiting for DFM job to finish")
#        job.wait_until_finished(timeout=job_completion_timeout())
#        carb.log_info("DFM pipeline finished")
#    except Exception as e:
#        import traceback
#        # Catch and log any error in pipeline execution
#        carb.log_error(f"Pipeline execution failed: {e}")
#        carb.log_error(f"Traceback: {traceback.format_exc()}")
#        raise e
#    finally:
#         # Signal the update task that we're completely done
#        req_queue.put("stop")
#
#        # Always clean up the session
#        session.close()

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



from http import HTTPStatus
from typing import List, Optional
from zoneinfo import ZoneInfo
import os

import omni.kit.app
import omni.usd
import carb
import carb.events
import carb.settings

from omni.kit.window.section import get_instance as get_section_instance

import omni.earth_2_command_center.app.core as earth_core
import omni.earth_2_command_center.app.core.features_api as FeaturesAPI

from .state import AppState, State
from ..utils.ovapi import OmniverseAPI
from ..utils.date import parse_datetime

from omni.earth_2_command_center.app.dfm.pipelines.gfs import GFSPipeline
from omni.earth_2_command_center.app.dfm.pipelines.era5 import ERA5Pipeline
from omni.earth_2_command_center.app.dfm.pipelines.hrrr import HRRRPipeline
from omni.earth_2_command_center.app.dfm.pipelines.fcn import FourCastNetPipeline
from omni.earth_2_command_center.app.dfm.pipelines.esri_topo import ESRITopoPipeline
from omni.earth_2_command_center.app.dfm.utils.exceptions import InputVariableError, InputTimeRangeError

app = OmniverseAPI()
state = AppState()

max_features = os.environ.get("K8S_E2CC_MAX_FEATURES", 8)
dfm_host = os.environ.get("K8S_E2CC_DFM_PROCESS_HOST", "http://localhost")
dfm_port = os.environ.get("K8S_E2CC_DFM_PROCESS_PORT", "8080")


# =======
# Utils
# =======
def toggle_feature(name: str, active: Optional[bool] = None, feature_type: type = None):
    """Toggles active state of all features with name 'name'

    Parameters
    ----------
    name : str
        Name of feature to toggle active state
    active : Optional[bool]
        State to set activeness of feature. When set to None, it will toggle the current state
    feature_type : type
        Type of Feature to filter. None to disable filtering by type

    Returns
    -------
    bool
        True if a feature was found and changed, False otherwise
    """
    # get features api
    features_api = earth_core.get_state().get_features_api()

    # get list of features to check
    features = None
    if feature_type is None:
        features = features_api.get_features()
    else:
        features = features_api.get_by_type(feature_type)

    # toggle active state of features in list
    state_changed = False
    for f in features:
        if f.name == name:
            f.active = active if (active is not None) else f.active
            state_changed = True

    return state_changed


def toggle_feature_id(
    id: int, active: Optional[bool] = None, feature_type: type = None
):
    """Toggles active state of all features at index

    Parameters
    ----------
    id : int
        Index of feature to toggle
    active : Optional[bool]
        State to set activeness of feature. When set to None, it will toggle the current state
    feature_type : type
        Type of Feature to filter. None to disable filtering by type

    Returns
    -------
    bool
        True if a feature was found and changed, False otherwise
    """
    # get features api
    features_api = earth_core.get_state().get_features_api()

    # get list of features to check
    features = None
    if feature_type is None:
        features = features_api.get_features()
    else:
        features = features_api.get_by_type(feature_type)

    # toggle active state of features in list
    state_changed = False
    if id < len(features):
        features[id].active = active if (active is not None) else features[id].active
        state_changed = True

    return state_changed


def delete_feature_id(id: int):
    """Delete feature based on id

    Parameters
    ----------
    id : int
        Index of feature to toggle

    Returns
    -------
    bool
        True if a feature was found and changed, False otherwise
    """
    # get features api
    features_api = earth_core.get_state().get_features_api()
    image_features = { i.id: i for i in features_api.get_features() }

    if id not in image_features:
        carb.log_error(f"Requested to delete feature with id {id} which does not exist")
        return False

    features_api.remove_feature(image_features[id])
    return True

def get_number_of_features() -> int:
    """Get the number of image features in the scene

    Returns
    -------
    int
        Number of features in the scene
    """
    features_api = earth_core.get_state().get_features_api()
    return len(features_api.get_image_features())

# =======
# APIs
# =======

# ===
# Data Federation
# ===

@app.request
def post_fetch(date_time: str, variable: str, source: str, render: bool = True) -> bool:
    """Executes are data fetch for the requested date, variable and source
    Data is then post processed and rendered on the

    Parameters
    ----------
    date_time : str
        Date time string
    variable : str
        Variable
    source : str
        Data source
    render : bool, optional
        Update scene with new data, by default True

    Returns
    -------
    State
        Current state of OV app
    """

    if state.value is HTTPStatus.PARTIAL_CONTENT:
        carb.log_warn("Fetch process still running!")
        return state.serialize()

    if get_number_of_features() >= max_features:
        carb.log_warn("Max number of features reached!")
        return state.serialize(
            value=HTTPStatus.METHOD_NOT_ALLOWED, description=f"Max number of features {max_features} reached!"
        )

    try:
        # The blueprint API is fixed to 3 days worth of data at a time
        # So num samples = 3 * 4 (4 timesteps per day)
        num_samples = 13
        dateobj = parse_datetime(date_time)
        if source.lower() == "gfs":
            carb.log_warn(f"Calling GFS execute {variable} and {date_time}")
            state.fetch_promise = GFSPipeline.execute(
                variable=variable,
                dateobj=dateobj,
                num_timesteps=num_samples,
                dfm_url=f"{dfm_host}:{dfm_port}",
            )
        elif source.lower() == "era5":
            carb.log_warn(f"Calling ERA5 execute {variable} and {date_time}")
            state.fetch_promise = ERA5Pipeline.execute(
                variable=variable,
                dateobj=dateobj,
                num_timesteps=num_samples,
                dfm_url=f"{dfm_host}:{dfm_port}"
            )
        elif source.lower() == "hrrr":
            carb.log_warn(f"Calling HRRR execute {variable} and {date_time}")
            state.fetch_promise = HRRRPipeline.execute(
                variable=variable,
                dateobj=dateobj,
                num_timesteps=num_samples,
                dfm_url=f"{dfm_host}:{dfm_port}"
            )
        elif source.lower() == "fcn":
            carb.log_warn(f"Calling FCN execute {variable} and {date_time}")
            state.fetch_promise = FourCastNetPipeline.execute(
               variable=variable,
                dateobj=dateobj,
                num_timesteps=num_samples,
                dfm_url=f"{dfm_host}:{dfm_port}"
            )
    except InputVariableError as e:
        carb.log_error(f"Input variable error {e}")
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST, description=str(e.message)
        )
    except InputTimeRangeError as e:
        carb.log_error(f"Time range error {e}")
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST, description=str(e.message)
        )
    except Exception as e:
        carb.log_error(f"Pipeline error {e}")
        return state.serialize(
            value=HTTPStatus.INTERNAL_SERVER_ERROR, description="Fetch request failed!"
        )

    return state.serialize()


# ===
# Visualize APIs
# ===


@app.request
def get_state() -> str:
    """Returns a json serializable representing current layers

    Returns
    -------
    str
        Current state of OV app
    """
    return state.serialize()


@app.request
def post_set_layer_order(layers: list[int]) -> bool:
    """Set order of layers being renders

    Parameters
    ----------
    layers : list[int]
        List of layer (feature) IDs in order to array

    Returns
    -------
    State
        Current state of OV app
    """

    features_api = earth_core.get_state().get_features_api()
    image_features = { i.id: i for i in features_api.get_image_features() }

    # get current positions
    image_features_pos = [features_api.get_feature_pos(f) for f in image_features.values()]
    # Sort highest to lowest, we only really care about making sure image layers have the right position in the global
    # stack invariant to permutation
    image_features_pos.sort()

    image_dict = {}
    for layer_id in layers:
        if layer_id in image_features:
            image_dict[image_features[layer_id]] = image_features_pos.pop(0)
        else:
            return state.serialize(
                value=HTTPStatus.INTERNAL_SERVER_ERROR, description=f"Got a invalid feature id. {layer_id} is not an image feature"
            )

    # reorder with a feature->new_pos mapping
    features_api.reorder_features(image_dict)

    # Check user has posted the right number of layer
    if len(layers) != len(state.state.layers):
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST, description="Did not recieve layer order list of correct size"
        )

    features_api = earth_core.get_state().get_features_api()
    excluded_layers = []
    image_layers = [None for _ in range(len(layers))]
    for i, feature in enumerate(features_api.get_features()):
        if feature.id in layers:
            image_layers[layers.index(int(feature.id))] = i
        else:
            excluded_layers.append(i)
    # TODO: Add check here to make sure all iamge layers are populated
    features_api.reorder_features(excluded_layers + image_layers)
    return state.serialize()


@app.request
def post_set_layer_visibility(feature_id: int, active: bool) -> State:
    """Set layer visibility

    Parameters
    ----------
    feature_id : int
        ID of the feature to toggle visibility
    active : bool
        True to show layer, False to hide

    Returns
    -------
    State
        Current state of OV app
    """
    features_api = earth_core.get_state().get_features_api()
    image_features = { i.id: i for i in features_api.get_features() }

    if feature_id not in image_features:
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST,
            description=f"Invalid feature id {feature_id}"
        )

    image_features[feature_id].active = active
    return state.serialize()


@app.request
def post_delete_layer(feature_id: int) -> State:
    """Delete layer if possible

    Parameters
    ----------
    layer : str
        Layer ID

    Returns
    -------
    State
        Current state of OV app
    """
    features_api = earth_core.get_state().get_features_api()
    image_features = [ i.id for i in features_api.get_image_features() ]
    if feature_id not in image_features:
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST, description="Invalid feature id"
        )

    delete_feature_id(feature_id)
    return state.serialize()


@app.request
def post_set_time_range(start_time: str, end_time: str) -> State:
    """Set the time range for visualization

    Parameters
    ----------
    start_time : str
        ISO formatted start time string
    end_time : str
        ISO formatted end time string

    Returns
    -------
    State
        Current state of OV app
    """
    try:
        start = parse_datetime(start_time).replace(tzinfo=ZoneInfo("UTC"))
        end = parse_datetime(end_time).replace(tzinfo=ZoneInfo("UTC"))

        if start >= end:
            return state.serialize(
                value=HTTPStatus.BAD_REQUEST,
                description="Start time must be before end time"
            )

        time_manager = earth_core.get_state().get_time_manager()
        time_manager.utc_start_time = start
        time_manager.utc_end_time = end
        time_manager._sync(start)  # Sync to start time
        return state.serialize()

    except Exception as e:
        carb.log_error(f"Error setting time range: {e}")
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST,
            description=f"Invalid datetime format: {str(e)}"
        )

@app.request
def post_set_time(date_time: str) -> State:
    """Set the current time for visualization if within the valid range

    Parameters
    ----------
    date_time : str
        ISO formatted datetime string

    Returns
    -------
    State
        Current state of OV app
    """
    try:
        target_time = parse_datetime(date_time).replace(tzinfo=ZoneInfo("UTC"))
        time_manager = earth_core.get_state().get_time_manager()

        # Check if time is within valid range
        if target_time < time_manager.utc_start_time or target_time > time_manager.utc_end_time:
            return state.serialize(
                value=HTTPStatus.BAD_REQUEST,
                description=f"Time {date_time} is outside valid range [{time_manager.utc_start_time} to {time_manager.utc_end_time}]"
            )

        # Set the current time
        time_manager.utc_time = target_time
        return state.serialize()

    except Exception as e:
        carb.log_error(f"Error setting time: {e}")
        return state.serialize(
            value=HTTPStatus.BAD_REQUEST,
            description=f"Invalid datetime format: {str(e)}"
        )

@app.request
def post_sun_light(active: bool) -> bool:
    """Toggle sun lights

    Parameters
    ----------
    active : bool
        If sun is active

    Returns
    -------
    State
        Current state of OV app
    """
    carb.log_info(f"Toggle sun {active}")
    toggle_feature("Sun", active, FeaturesAPI.Sun)
    state.set_toggle("Sun", active)
    state.set_toggle("Atmosphere", active)
    return state.serialize()


@app.request
def post_atmosphere(active: bool) -> bool:
    """Toggle atmosphere

    Parameters
    ----------
    active : bool
        If atmosphere is active

    Returns
    -------
    State
        Current state of OV app
    """
    carb.log_info(f"Toggle atmosphere {active}")
    toggle_feature("Atmosphere", active, FeaturesAPI.Light)
    state.set_toggle("Sun", active)
    state.set_toggle("Atmosphere", active)
    return state.serialize()


@app.request
def post_topography(active: bool) -> bool:
    """
    Fetch and add topography layer from ESRI

    Parameters
    ----------
    active : bool
        If topography is active or not

    Returns
    -------
    State
        Current state of OV app
    """
    if active:
        # For toggle on, fetch the topography layer from ESRI
        if state.value is HTTPStatus.PARTIAL_CONTENT:
            carb.log_warn("Fetch process still running!")
            return state.serialize()

        if get_number_of_features() >= max_features:
            carb.log_warn("Max number of features reached!")
            return state.serialize(
                value=HTTPStatus.METHOD_NOT_ALLOWED, description=f"Max number of features {max_features} reached!"
            )
        state.fetch_promise = ESRITopoPipeline.execute(processing="ellipsoidal_height", dfm_url=f"{dfm_host}:{dfm_port}")
    else:
        # For toggle off, delete the topography layer
        features_api = earth_core.get_state().get_features_api()
        for f in features_api.get_features():
            if "ESRITopography" in f.name:
                delete_feature_id(f.id)

    return state.serialize()

@app.request
def post_coastlines(active: bool) -> bool:
    """Toggle coastlines

    Parameters
    ----------
    active : bool
        If coastlines is active

    Returns
    -------
    State
        Current state of OV app
    """
    carb.log_info(f"Toggle Continents Outline {active}")
    toggle_feature("Continents Outline", active, FeaturesAPI.Curves)
    state.set_toggle("Continents Outline", active)
    return state.serialize()


def initialize() -> bool:
    """
    Called by the kit app on initial load once
    (Something like globe init)
    """

    async def async_init():
        carb.log_info("car_controller initializing")
        # global GlobalState
        # HACK:
        # https://nvidia.slack.com/archives/CCSV6PBR6/p1728341311931449
        # Need to toggle the section tool window at least once
        # to make sure set_slice_state works
        # While it's open, set any relevant settings
        # Wait a few frames before closing it
        # initialize_aysnc_car_selction_handler()
        settings = carb.settings.get_settings()
        get_section_instance().show_window(None, True)
        # settings.set(SETTING_SECTION_ALWAYS_DISPLAY, False)
        # settings.set(SETTING_SECTION_ENABLED, False)
        # settings.set(SETTING_SECTION_LIGHT, False)
        await wait_for_frames(10)
        get_section_instance().show_window(None, False)

        # Start the zmq client and set the app state
        # Flipped true for the new data, false for the old data
        flipped = True
        sdf_range = [-10.0, 0.0] if flipped else [0.0, 10.0]
        settings = carb.settings.get_settings()
        # settings.set("exts/omni.cgns/distance_ranges", sdf_range)
        # initialize_streamline_mode()
        # reset()
        await wait_for_frames(1000)

    run_task_and_block(async_init)
    return True


def run_task_and_block(fn):
    omni.kit.async_engine.run_coroutine(fn())


async def wait_for_frames(n: int):
    carb.log_info(f"Waiting for {n} frames...")
    for i in range(0, n):
        await omni.kit.app.get_app().next_update_async()
    return

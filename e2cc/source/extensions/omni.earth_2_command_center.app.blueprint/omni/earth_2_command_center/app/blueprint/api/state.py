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
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import hashlib

import carb

import omni.earth_2_command_center.app.core as earth_core
from omni.earth_2_command_center.app.core.features.image import Image
from omni.earth_2_command_center.app.core.features_api import FeatureChange

class ColorMap(BaseModel):
    """Configuration class that holds JSON serializable data about colormap"""

    label: str = Field("binary", description="Color map")
    minimum: int = Field(0, description="Color map minimum")
    maximum: int = Field(1, description="Color map maximum")
    unit: str = Field("", description="")

class Layer(BaseModel):
    """Configuration class that holds JSON serializable data about layers"""

    variable_label: str = Field(..., description="")
    source_label: str = Field(..., description="")
    type_label: str = Field("static", description="")
    date_time: datetime | None = None
    color_map: ColorMap = ColorMap()
    active: bool = Field(True, description="")
    feature_id: int | None = None


class Toggle(BaseModel):
    """Configuration class that holds JSON serializable data about toggle controls"""

    label: str = Field(..., description="")
    event: str = Field(..., description="")
    active: bool = Field(True, description="")


class TimeManager(BaseModel):
    """Configuration class that holds JSON serializable data about time manager state"""
    start: datetime | None = Field(None, description="Start time of timeline")
    end: datetime | None = Field(None, description="End time of timeline")


class State(BaseModel):
    """Configuration class for the entire blueprint OV app"""

    layers: list[Layer] = Field(..., description="Feature layers present")
    toggles: list[Toggle] = Field(..., description="Toggle Controls present")
    time_manager: TimeManager = Field(default_factory=TimeManager, description="Time manager state")


class Message(BaseModel):
    """Message model"""

    value: int = Field(HTTPStatus.OK, description="Status value of message")
    description: str = Field(
        HTTPStatus.OK.description, description="Description of message"
    )
    state: State = Field(..., description="Toggle Controls present")


class AppState:

    _image_features: dict[str, Image] = {}
    _cb_subscription = None

    def __init__(self):
        self.state = State(
            layers=[],
            toggles=[],
            time_manager=TimeManager(),
        )
        self.sync_layers()
        self.sync_time_manager()
        self.sync_toggle_buttons()
        self.fetch_promise = None
        AppState._register_cb()

    @classmethod
    def _on_feature_event(cls, event):
        change = event.payload['change']
        if change['id'] == FeatureChange.FEATURE_REMOVE['id']:
            # A feature has been removed, we need to figure out which one and remove it
            sender_id = event.sender
            for key in cls._image_features:
                if cls._image_features[key].image.id == sender_id:
                    del cls._image_features[key]
                    break
            earth_core.get_state().get_time_manager().include_all_features()

    @classmethod
    def _register_cb(cls):
        if not cls._cb_subscription:
            feature_event_stream = earth_core.get_state().get_features_api().get_event_stream()
            cls._cb_subscription = feature_event_stream.create_subscription_to_pop(cls._on_feature_event)


    def sync_layers(self) -> None:
        """Creates layer list based on current image features in Earth-2 CC"""
        features_api = earth_core.get_state().get_features_api()
        features = [
            feature
            for feature in features_api.get_features()
            if isinstance(feature, Image)
        ]

        self.state.layers = [
            Layer(
                variable_label=feature.meta.get("variable_label", "Blue Marble"),
                source_label=feature.meta.get("source_label", "NASA"),
                type_label=feature.meta.get("type_label", "static"),
                date_time=feature.meta.get("date_time", None),
                color_map = ColorMap(
                    label=feature.meta.get("cmap_label", "binary"),
                    minimum=feature.meta.get("cmap_min", 0),
                    maximum=feature.meta.get("cmap_max", 1),
                    unit=feature.meta.get("cmap_unit", ""),
                ),
                active=feature.active,
                feature_id=feature.meta.get("feature_id", int(feature.id)),
            )
            for feature in features
        ]

    def sync_time_manager(self) -> None:
        """Syncs time manager state with current TimeManager values"""
        time_manager = earth_core.get_state().get_time_manager()
        self.state.time_manager.start = time_manager.utc_start_time
        self.state.time_manager.end = time_manager.utc_end_time

    def sync_toggle_buttons(self) -> None:
        """Syncs toggle buttons with current toggle state"""
        features_api = earth_core.get_state().get_features_api()
        # Defaults
        toggles=[
            Toggle(label="Sun", event="post_sun_light", active=True),
            Toggle(label="Atmosphere", event="post_atmosphere", active=True),
            Toggle(
                label="Continents Outline", event="post_coastlines", active=False
            ),
            Toggle(label="Topography", event="post_topography", active=False)
        ]
        # Sync any active features
        for f in features_api.get_features():
            if f.name == "Sun":
                toggles[0] = Toggle(label="Sun", event="post_sun_light", active=f.active)
            elif f.name == "Atmosphere":
                toggles[1] = Toggle(label="Atmosphere", event="post_atmosphere", active=f.active)
            elif f.name == "Continents Outline":
                toggles[2] = Toggle(label="Continents Outline", event="post_coastlines", active=f.active)
            elif "ESRITopography" in f.name:
                toggles[3]  = Toggle(label="Topography", event="post_topography", active=f.active)
        self.state.toggles = toggles

    def set_layer_visibility(self, feature_id: str, active: bool):
        for layer in self.state.layers:
            if layer.meta.get("feature_id", str(layer.id)) == str(feature_id):
                layer.active = active
                break

    def set_toggle(self, label: str, active: bool):
        for toggle in self.state.toggles:
            if toggle.label == label:
                toggle.active = active
                break
    @property
    def value(self) -> int:
        if self.fetch_promise is None:
            return HTTPStatus.OK
        elif not self.fetch_promise.done():
            return HTTPStatus.PARTIAL_CONTENT
        else:
            return HTTPStatus.OK

    @property
    def description(self) -> str:
        match self.value:
            case HTTPStatus.OK:
                return HTTPStatus.OK.description
            case HTTPStatus.PARTIAL_CONTENT:
                return "Fetch request already running"
            case _:
                return "Unknown state code"

    def serialize(
        self, value: int | None = None, description: str | None = None
    ) -> str:
        """Returns JSON serialized message with app state

        Parameters
        ----------
        value : int, optional
            message value over ride, by default None
        description : str, optional
            message description over ride, by default None

        Returns
        -------
        str
            Serialized message object
        """
        value_out = self.value
        description_out = self.description
        # Over rides
        if value:
            value_out = value
        if description:
            description_out = description

        # Re-sync state
        self.sync_layers()
        self.sync_time_manager()
        self.sync_toggle_buttons()

        message = Message(value=value_out, description=description_out, state=self.state)
        return message.model_dump(mode="json")

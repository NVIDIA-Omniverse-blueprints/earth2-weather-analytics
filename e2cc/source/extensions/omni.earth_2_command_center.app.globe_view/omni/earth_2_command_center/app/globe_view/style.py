# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



__all__ = [
    "FEATURE_PANEL",
    "NAVIGATION_PANEL"
]

from omni.ui import SliderDrawMode

EXT_TOKEN = "${omni.earth_2_command_center.app.globe_view}"

############################################
# COLOR
############################################
_LIGHT = 0xFF9E9E9E
_LIGHT_A = 0xAA9E9E9E
_MID = 0xFF535354
_MID_A = 0x55535354
_DARK = 0xFF3A3A3A
_DARK_A = 0xAA2A2825
_BLUE = 0xFFC5911A
_BLUE_A = 0xAAC5911A

############################################
# FONT
############################################
_FONT = f"{EXT_TOKEN}/data/fonts/OpenSans-SemiBold.ttf"
_FONT_SIZE = 18

############################################
# ICONS
############################################
_VISIBLE_ON = f"{EXT_TOKEN}/data/icons/visible_on_tint.svg"
_VISIBLE_OFF = f"{EXT_TOKEN}/data/icons/visible_off_tint.svg"
_ZOOM_IN = f"{EXT_TOKEN}/data/icons/navThumb_zoomIn_tint.svg"
_ZOOM_OUT = f"{EXT_TOKEN}/data/icons/navThumb_zoomOut_tint.svg"
_HOME = f"{EXT_TOKEN}/data/icons/navHome_tint.svg"
_SYNC = f"{EXT_TOKEN}/data/icons/sync.svg"
_INFO = f"{EXT_TOKEN}/data/icons/info_tint.svg"
_PLAY = f"{EXT_TOKEN}/data/icons/play.svg"
_PAUSE = f"{EXT_TOKEN}/data/icons/pause_dark.svg"
_OPTIONS = f"{EXT_TOKEN}/data/icons/options.svg"
_ADD = f"{EXT_TOKEN}/data/icons/add.svg"
#==========================================#

############################################
# FEATURE PANEL
############################################
FEATURE_PANEL = {
    "Line": {"margin_width": 4, "color": _MID_A},
    "Rectangle::foreground": {"background_color": _DARK_A},
    "Rectangle::background": {"background_color": _DARK_A, "border_radius": 3},
    "VStack::features": {"margin": 12},
    "HStack::feature_row": {"margin_width": 4},
    "Label": {"font": _FONT, "font_size": _FONT_SIZE, "color": _LIGHT},
    "Button": {"background_color": 0x0, "padding": 0},
    "Button:checked": {"background_color": 0x0},
    "Button:hovered": {"background_color": 0x0},
    "Button:pressed": {"background_color": 0x0},
    "Button.Image": {"background_color": 0x0},
    "Button.Image::visible_toggle": {"image_url": _VISIBLE_OFF, "color": _MID},
    "Button.Image::visible_toggle:hovered": {"color": _BLUE_A},
    "Button.Image::visible_toggle:checked": {"image_url": _VISIBLE_ON, "color": _LIGHT},
    "Button.Image::visible_toggle:pressed": {"color": _BLUE_A},
    "ComboBox": {
        "background_color": _DARK_A,
        "selected_color": _BLUE_A,
        "color": _LIGHT,
        "font": _FONT,
        "font_size": _FONT_SIZE,
        "margin_width": 4,
        "padding": 0,
    },
    "ComboBox:hovered": {"background_color": _DARK}
}

############################################
# NAVIGATION PANEL
############################################
NAVIGATION_PANEL = {
    "Rectangle::background": {"background_color": _DARK_A, "border_radius": 3},
    "Button": {"background_color": 0x0},
    "Button:hovered": {"background_color": 0x0},
    "Button:pressed": {"background_color": 0x0},
    "Button.Image": {"background_color": 0x0},
    "Button.Image:hovered": {"color": _BLUE_A},
    "Button.Image:pressed": {"color": _BLUE_A},
    "Button.Image::nav_zoom_in": {"image_url": _ZOOM_IN, "color": _LIGHT},
    "Button.Image::nav_zoom_out": {"image_url": _ZOOM_OUT, "color": _LIGHT},
    "Button.Image::nav_home": {"image_url": _HOME, "color": _LIGHT},
    "Button.Image::refresh": {"image_url": _SYNC, "color": _LIGHT},
    "Button.Image::feature_properties": {"image_url": _OPTIONS, "color": _LIGHT},
    "Button.Image::add": {"image_url": _ADD, "color": _LIGHT},
}

############################################
# INFO PANEL
############################################
INFO_PANEL = {
    "font": _FONT,
    "font_size": _FONT_SIZE,
    "Rectangle::background": {"background_color": _DARK_A, "border_radius": 3},
    "Label::info_text": {"margin": 12, "color": _LIGHT},
    "Label::info_source": {"color": _DARK},
    "Button": {"background_color": _DARK_A, "margin": 0},
    "Button:hovered": {"background_color": _DARK_A},
    "Button:pressed": {"background_color": _DARK_A},
    "Button:checked": {"background_color": _DARK_A},
    "Button.Image": {"background_color": 0x0},
    "Button.Image:hovered": {"color": _BLUE_A},
    "Button.Image:pressed": {"color": _BLUE_A},
    "Button.Image:checked": {"color": _BLUE_A},
    "Button.Image::info_button": {"image_url": _INFO, "color": _LIGHT},
}

INFO_TEXT = """This simulation was generated from historical data and enables real time visualization of global weather patterns
over a 24 hour day. It is accurate enough to reproduce the famed Blue Marble image of the Earth.
\nMoving forward, we'll have the ability to scrub global weather patterns at points in time from the past into the present."""

############################################
# DATE PANEL
############################################
DATE_PANEL = {
    "Rectangle": {"background_color": _DARK_A, "border_radius": 3},
    "Button": {"background_color": 0x0, "margin_height": 5, "margin_width": 5,},
    "Line::timeline": {"color": _LIGHT},
    "Circle": {"background_color": _MID},
    "Circle:checked": {"background_color": _BLUE},
    "Label": {"color": _LIGHT}
}

############################################
# PLAYBACK PANEL
############################################
# The main style dict
PLAYBACK_PANEL = {
    "Rectangle": {"background_color": _DARK_A, "border_radius": 3},
    "Button": { "background_color": 0x0, "margin_height": 0.5, "margin_width": 0.5},
    "Button:hovered": {"background_color": 0x0},
    "Button:pressed": {"background_color": 0x0},
    "Button:checked": {"background_color": 0x0},
    "Button.Image::play": {"image_url": _PLAY},
    "Button.Image::play:checked": {"image_url": _PAUSE},
    "Slider": { "background_color": _BLUE, "color": _LIGHT, "margin_height": 2},
    "Slider::timeline": {
        "background_color": _MID_A,
        "color": _LIGHT_A,
        "draw_mode": SliderDrawMode.HANDLE,
        "font_size": 20,
        "secondary_color": _BLUE_A,
        "padding": -0.5,
        "margin_height": 4,
        "margin_width": 2,
        "border_width": 0,
        "border_radius": 10,
    },
    "Label": {"color": _LIGHT},
    "Label::date": {"color": _BLUE}
}

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



from omni import ui

KIT_GREEN = 0xFF8A8777
LABEL_PADDING = 110

EXT_TOKEN = "${omni.earth_2_command_center.app.dfm}"

############################################
# ICONS
############################################
ICON_PATHS = {
    "cancel": f"{EXT_TOKEN}/data/icons/cancel.svg",
    "sync": f"{EXT_TOKEN}/data/icons/sync.svg",
}

WINDOW_STYLE = {
    "Window": {"background_color": 0xFF444444},
    "Button": {
        "background_color": 0xFF292929,
        "margin": 3,
        "padding": 3,
        "border_radius": 2,
    },
    "Button.Label": {"color": 0xFFCCCCCC},
    "Button:hovered": {"background_color": 0xFF9E9E9E},
    "Button:pressed": {"background_color": 0xC22A8778},
    "VStack::main_v_stack": {
        "secondary_color": 0x0,
        "margin_width": 10,
        "margin_height": 0,
    },
    "VStack::frame_v_stack": {"margin_width": 15},
    "Rectangle::frame_background": {"background_color": 0xFF343432, "border_radius": 5},
    "Field::models": {
        "background_color": 0xFF23211F,
        "font_size": 14,
        "color": 0xFFAAAAAA,
        "border_radius": 4.0,
    },
    "Frame": {"background_color": 0xFFAAAAAA},
    "Label::transform": {"font_size": 12, "color": 0xFF8A8777},
    "Circle::transform": {"background_color": 0x558A8777},
    "Field::transform": {
        "background_color": 0xFF23211F,
        "border_radius": 3,
        "corner_flag": ui.CornerFlag.RIGHT,
        "font_size": 12,
    },
    "Slider::transform": {
        "background_color": 0xFF23211F,
        "border_radius": 3,
        "draw_mode": ui.SliderDrawMode.DRAG,
        "corner_flag": ui.CornerFlag.RIGHT,
        "font_size": 14,
    },
    "Label::transform_label": {"font_size": 12, "color": 0xFFDDDDDD},
    "Label": {"font_size": 12, "color": 0xFF8A8777},
    "Label::label": {"font_size": 14, "color": 0xFF8A8777},
    "Label::title": {"font_size": 14, "color": 0xFFAAAAAA},
    "Triangle::title": {"background_color": 0xFFAAAAAA},
    "ComboBox::path": {
        "font_size": 12,
        "secondary_color": 0xFF23211F,
        "color": 0xFFAAAAAA,
    },
    "ComboBox::choices": {
        "font_size": 12,
        "color": 0xFFAAAAAA,
        "background_color": 0xFF23211F,
        "secondary_color": 0xFF23211F,
    },
    "ComboBox:hovered:choices": {
        "background_color": 0xFF33312F,
        "secondary_color": 0xFF33312F,
    },
    "Slider::value_less": {
        "font_size": 12,
        "color": 0x0,
        "border_radius": 5,
        "background_color": 0xFF23211F,
        "secondary_color": KIT_GREEN,
        "border_color": 0xFFAAFFFF,
        "border_width": 0,
    },
    "Slider::value": {
        "font_size": 14,
        "color": 0xFFAAAAAA,
        "border_radius": 5,
        "background_color": 0xFF23211F,
        "secondary_color": KIT_GREEN,
    },
    "Rectangle::add": {"background_color": 0xFF23211F},
    "Rectangle:hovered:add": {"background_color": 0xFF73414F},
    "CheckBox::greenCheck": {
        "font_size": 10,
        "background_color": KIT_GREEN,
        "color": 0xFF23211F,
    },
    "CheckBox::whiteCheck": {
        "font_size": 10,
        "background_color": 0xFFDDDDDD,
        "color": 0xFF23211F,
    },
    "Slider::colorField": {
        "background_color": 0xFF23211F,
        "font_size": 14,
        "color": 0xFF8A8777,
    },
    # Frame
    "CollapsableFrame::standard_collapsable": {
        "background_color": 0xFF343432,
        "secondary_color": 0xFF343432,
        "font_size": 16,
        "border_radius": 2.0,
        "border_color": 0x0,
        "border_width": 0,
    },
    "CollapsableFrame:hovered:standard_collapsable": {"secondary_color": 0xFFFBF1E5},
    "CollapsableFrame:pressed:standard_collapsable": {"secondary_color": 0xFFF7E4CC},
}

CollapsableFrame_style = {
    "CollapsableFrame": {
        "background_color": 0xFF343432,
        "secondary_color": 0xFF343432,
        "color": 0xFFAAAAAA,
        "border_radius": 4.0,
        "border_color": 0x0,
        "border_width": 0,
        "font_size": 14,
        "padding": 0,
    },
    "HStack::header": {"margin": 5},
    "CollapsableFrame:hovered": {"secondary_color": 0xFF3A3A3A},
    "CollapsableFrame:pressed": {"secondary_color": 0xFF343432},
}

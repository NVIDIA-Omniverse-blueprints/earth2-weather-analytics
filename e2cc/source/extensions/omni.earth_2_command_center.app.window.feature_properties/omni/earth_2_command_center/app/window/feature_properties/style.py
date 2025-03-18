# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



EXT_TOKEN = "${omni.earth_2_command_center.app.window.feature_properties}"

############################################
# ICONS
############################################
ICON_PATHS = {
        'add':f"{EXT_TOKEN}/data/icons/add.svg",
        'cancel':f"{EXT_TOKEN}/data/icons/cancel.svg",
        'delete':f"{EXT_TOKEN}/data/icons/delete.svg",
        'edit':f"{EXT_TOKEN}/data/icons/edit.svg",
        'remove':f"{EXT_TOKEN}/data/icons/remove.svg",
        'sync':f"{EXT_TOKEN}/data/icons/sync.svg",
        'time_bracket':f"{EXT_TOKEN}/data/icons/time_bracket.svg",
        }

STYLES = {
        'Button': {
            'background_color':0x00FFFFFF},
        'Button:hovered': {
            'background_color':0x44FFFFFF}
        }

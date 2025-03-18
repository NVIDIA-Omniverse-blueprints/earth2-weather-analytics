# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ['create_unique_prim_path', 'toggle_visibility']

import uuid
from pxr import UsdGeom, Sdf, Tf, Usd, Gf

import carb

def create_unique_prim_path(base_path = Sdf.Path('/World/globe_view'), prefix = 'prim'):
    return base_path.AppendChild(f'{prefix}_{uuid.uuid4().hex}')

# toggle USD Imageable viility attribute
def toggle_visibility(stage, path, value=None):
    prim = UsdGeom.Imageable(stage.GetPrimAtPath(path))
    if not prim:
        carb.log_warn(f'Could not find prim to toggle visibility: {path}')
        return
    vis_attr = prim.GetVisibilityAttr()
    if value is not None:
        vis_attr.Set('inherited' if value else 'invisible')
    else:
        if vis_attr.Get() == 'invisible':
            vis_attr.Set('inherited')
        else:
            vis_attr.Set('invisible')


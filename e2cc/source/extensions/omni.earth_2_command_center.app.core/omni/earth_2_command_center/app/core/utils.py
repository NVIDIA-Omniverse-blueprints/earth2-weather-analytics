# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'pinpoints_to_affine_mapping', 'latlong_rect_to_affine_mapping', 'affine_mapping_to_shader_param_value' ]

import numpy as np

# source points in image space to target points in latlong (radians)
def pinpoints_to_affine_mapping(source, target, is_in_radians=True):
    if len(source) != len(target):
        raise RuntimeError('source and target points length mismatch')
    if len(source) < 3:
        raise RuntimeError('need 3 points')

    if not is_in_radians:
        target = target.copy()
        for idx,p in enumerate(target):
            target[idx] = np.deg2rad(p.astype(np.float32))

    L = np.array([
        target[0:3,0].transpose(),
        target[0:3,1].transpose(),
        [1, 1, 1]], dtype=np.float32)
    L_inv = np.linalg.inv(L)

    U = np.array([
        source[0:3,0].transpose(),
        source[0:3,1].transpose()
        ], dtype=np.float32)
    A_inv = np.dot(U, L_inv)

    return A_inv

def latlong_rect_to_affine_mapping(lon_min, lon_max, lat_min, lat_max, is_in_radians=True):
    # NOTE: we know the solution analytically but this isn't called frequently
    #       so doing a 3x3 matrix inversion is of no concern. However, when the
    #       latlon window gets very small, we might need to care about conditioning.
    source = np.array(np.array([[0,0], [1,1], [0,1]], dtype=np.float32))
    target = np.array(np.array([[lon_min, lat_min], [lon_max, lat_max], [lon_min, lat_max]], dtype=np.float32))
    result = pinpoints_to_affine_mapping(source, target, is_in_radians)
    return result

def affine_mapping_to_shader_param_value(mapping):
    return mapping.flatten()[0:6].tolist()


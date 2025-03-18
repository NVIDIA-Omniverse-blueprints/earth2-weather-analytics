# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import json
import os

import png

import numpy as np

def write_paraview_colormap(json_file_path):

    colormap_name, _ = os.path.splitext(os.path.basename(json_file_path))

    with open(json_file_path, 'r') as f:
        cmdata = json.load(f)


    for entry in cmdata:
        name: str = entry["Name"]
        name_sanitized = name.replace(' ', '').replace('(','').replace(')','')
        png_path = f'./{name_sanitized}.png'

        rgb_points = np.array(entry['RGBPoints']).astype(np.float32).reshape((-1, 4))
        colors = rgb_points[:,1:4]
        n = colors.shape[0]

        pixels = np.zeros((colors.shape[0], 4))
        pixels[:,0:3] = colors
        if '(divergent)' in name:
            pixels[:n // 2, 3] = np.linspace(1., 0., n // 2, endpoint=False)
            pixels[n // 2:, 3] = np.linspace(0., 1., n - n // 2)
        else:
            pixels[:, 3] = np.linspace(0., 1., n)

        pixels *= 256 * 256 - 1
        pixels = pixels.astype(np.uint16).reshape((1, -1))

        png.from_array(pixels, mode="RGBA;16").save(png_path)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('json_file', type=str)
    args = parser.parse_args()


    write_paraview_colormap(args.json_file)

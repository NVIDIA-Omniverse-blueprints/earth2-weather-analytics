# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import sys
import csv
import png
import numpy as np
import matplotlib as mpl

def write_matplotlib_colormap(colormap_name, png_path):
    colormap = mpl.colormaps[colormap_name]
    if not colormap:
        raise RuntimeError(f'Could not retrieve colormap: "{colormap_name}"')
    num_rows = colormap.N
    pixels = np.ndarray((1,num_rows*4), dtype=np.float32)
    for i in range(num_rows):
        x = i/(num_rows-1)
        val = colormap(x)
        pixels[0,4*i:4*i+4] = val
    
    pixels *= 256*256-1
    pixels = pixels.astype(np.uint16)
    png.from_array(pixels, mode="RGBA;16").save(png_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise RuntimeError('Argument missing')
    
    colormap_name = sys.argv[1]
    png_path = f'./{colormap_name}.png'
    
    write_matplotlib_colormap(colormap_name, png_path)

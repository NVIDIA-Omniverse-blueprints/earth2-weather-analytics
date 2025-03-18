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

if len(sys.argv) < 3:
    raise RuntimeError('Argument missing')

file_path = sys.argv[1]
png_path = sys.argv[2]

pixels = np.ndarray((1,256*3), dtype=np.float32)

with open(file_path) as file:
    csv_data = csv.reader(file)
    for i,r in enumerate(csv_data):
        pixels[0,3*i:3*i+3] = r
pixels *= 256
pixels = pixels.astype(np.uint8)
print(pixels)

png.from_array(pixels, mode="RGB").save(png_path)



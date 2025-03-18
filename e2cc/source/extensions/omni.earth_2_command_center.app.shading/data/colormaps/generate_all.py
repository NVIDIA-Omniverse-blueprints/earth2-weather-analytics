# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import matplotlib as mpl
import cmocean

from write_matplotlib_colormap import *
from write_cmocean_colormap import *

if __name__ == '__main__':
    colormaps = mpl.colormaps()
    for c in colormaps:
        print(f'Processing "{c}"')
        write_matplotlib_colormap(c, f'{c}.png')

    #colormaps = cmocean.cm.cmapnames
    #for c in colormaps:
    #    print(f'Processing "{c}"')
    #    write_cmocean_colormap(c, f'{c}.png')



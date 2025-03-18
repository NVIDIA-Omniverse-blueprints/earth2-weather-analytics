# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import carb
import carb.settings

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence, DiamondTimestampedSequence

import omni.usd
from pxr import Usd, UsdGeom, Tf

import numpy as np
from functools import partial

def add_diamond_sequence_callback(ext, var_name):
    base = carb.settings.get_settings().get_as_string("/exts/omni.earth_2_command_center.app.test_sequence/icon_blue_marble_base")
    #path_pattern = ext.get_base_url()+'textures/diamond/sfcwind_test_001/k{idx}/sfcwind_t0.jpg'
    #path_pattern = base+'/{var_name}/{idx}/{timestamp}.jpg'
    path_pattern = base+'/{var_name}_q85/{idx}/{timestamp}_q85.jpg'
    #path_pattern = '/home/phadorn/persistent_tmp/datasets/ICON/R2B11/sfcwind/{idx}/{timestamp}.jpg'

    import datetime
    start = datetime.datetime(year=1972, month=12, day=7, hour=0, minute=2)
    delta = datetime.timedelta(seconds=120)
    deltas_per_step = 1
    end = datetime.datetime(year=1972, month=12, day=7, hour=23, minute=58)

    # Create Timestamped Sequence
    seq = DiamondTimestampedSequence()
    idx_list = ext.get_next_idx()

    # create a unique url for this sequence
    import uuid
    for s in seq.tex_list():
        s.target_url = f'dynamic://test_sequence_{uuid.uuid4()}'
        #carb.log_warn(f'Set up dynamic texture with {s.target_url}')

    cur_utc = start
    trans_table = str.maketrans({'T':'_', ':':'-'})

    to_insert_list = []
    while cur_utc <= end:
        to_insert_list.append((cur_utc,
            [path_pattern.format(var_name=var_name, idx=i, timestamp=cur_utc.isoformat().translate(trans_table)) for i in range(10)]))
        cur_utc += delta*deltas_per_step
    seq.insert_multiple(to_insert_list)

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()
    img.alpha_sources = [s.target_url for s in seq.tex_list()]
    #img.sources = img.alpha_sources

    # configure and add feature
    img.projection = 'diamond'
    remapping = img.remapping
    if var_name == 'cloud':
        img.name = f'ICON Clouds'
        remapping['output_max'] = 1.5
        remapping['output_gamma'] = 0.54
    elif var_name == 'sfcwind':
        img.name = f'ICON Wind Magnitude'
        img.colormap = 'cmo.deep_r'
        remapping['input_max'] = 0.8
        remapping['output_gamma'] = 1.2
    img.remapping = remapping

    img.time_coverage = seq.time_coverage

    ext.add_sequence(seq, img)

    features_api = get_state().get_features_api().add_feature(img)
    get_state().get_time_manager().include_all_features(playback_duration=60)

    get_state().get_icon_helper().register_diamond_list(img, seq.tex_list())

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

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence

import numpy as np

def _add_test_sequence_common(ext, path_pattern):
    # Create Timestamped Sequence
    seq = TimestampedSequence()
    idx = ext.get_next_idx()

    # create a unique url for this sequence
    import uuid
    seq.target_url = f'dynamic://test_sequence_{uuid.uuid4()}'

    import datetime
    start_time = datetime.datetime(year=1972, month=12, day=1)
    frame_skip = 10
    start_frame = 0
    end_frame = 700
    time_delta = datetime.timedelta(minutes = 2)
    to_insert = []
    for i in range(start_frame, end_frame+1, frame_skip):
        cur_utc = start_time + time_delta*i
        to_insert.append((cur_utc, path_pattern.format(frame=i)))
    seq.insert_multiple(to_insert)

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()
    img.alpha_sources = [seq.target_url]
    img.flip_v = True
    import numpy as np
    img.longitudinal_offset = -np.pi
    img.time_coverage = seq.time_coverage

    # keep references to the sequence and the feature
    ext.add_sequence(seq, img)

    return seq, idx, img

def add_blue_marble_clouds_callback(ext):
    base_url = carb.settings.get_settings().get_as_string("/exts/omni.earth_2_command_center.app.test_sequence/blue_marble_base")
    path_pattern = base_url + 'textures/CMIP6/cloud1.25/cloud_1km_{frame}.jpg'
    seq, idx, img = _add_test_sequence_common(ext, path_pattern)

    # configure and add feature
    img.name = f'Blue Marble Cloud Coverage'
    remapping = img.remapping
    remapping['input_max'] = 0.5
    remapping['output_gamma'] = 1.5
    img.remapping = remapping

    features_api = get_state().get_features_api().add_feature(img)
    # update global timeline to cover all active features
    get_state().get_time_manager().include_all_features(playback_duration=4)

def add_blue_marble_wind_callback(ext):
    base_url = carb.settings.get_settings().get_as_string("/exts/omni.earth_2_command_center.app.test_sequence/blue_marble_base")
    path_pattern = base_url + 'textures/CMIP6/sfcwind1.25/r2b11_sfcwind_{frame}.jpg'
    seq, idx, img = _add_test_sequence_common(ext, path_pattern)

    # configure and add feature
    img.name = f'Blue Marble Wind Magnitude'
    remapping = img.remapping
    remapping['input_max'] = 0.9
    remapping['output_gamma'] = 2.0
    img.remapping = remapping
    img.colormap = 'cmo.deep_r'

    features_api = get_state().get_features_api().add_feature(img)
    # update global timeline to cover all active features
    get_state().get_time_manager().include_all_features(playback_duration=4)

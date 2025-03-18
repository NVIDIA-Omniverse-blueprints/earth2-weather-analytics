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

PATH_PATTERN   = '/home/phadorn/Downloads/twc3km/twc3km_{varname}_{frame:03d}.jpg'
META_DATA_PATH = '/home/phadorn/Downloads/twc3km/meta.json'

def numpy_datetime64_to_datetime(val):
    # I'm assuming datetime64[ns] represents ns since epoch=1970-1-1_00:00
    import datetime
    return datetime.datetime(1970,1,1,0,0) + datetime.timedelta(microseconds=(val.astype(int)*1e-3))

def _add_test_sequence_common(ext, path_pattern, meta_data_path, varname):
    import json
    meta_data = None
    with open(meta_data_path, 'r') as file:
        meta_data = json.load(file)
    meta_data['time'] = np.array(meta_data['time'], dtype='datetime64[ns]')

    # Create Timestamped Sequence
    seq = TimestampedSequence()
    idx = ext.get_next_idx()

    # create a unique url for this sequence
    import uuid
    seq.target_url = f'dynamic://test_sequence_{uuid.uuid4()}'

    num_frames = len(meta_data['time'])

    import datetime
    frame_skip = 1
    start_frame = 0
    end_frame = num_frames-1

    to_insert = []
    for i in range(start_frame, end_frame+1, frame_skip):
        cur_utc = numpy_datetime64_to_datetime(meta_data['time'][i])
        to_insert.append((cur_utc, path_pattern.format(frame=i, varname=varname)))
    seq.insert_multiple(to_insert)

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()
    img.alpha_sources = [seq.target_url]
    img.time_coverage = seq.time_coverage

    # keep references to the sequence and the feature
    ext.add_sequence(seq, img)

    return seq, idx, img

def _add_test_sequence_common_footer(ext, img):
    features_api = get_state().get_features_api().add_feature(img)
    # update global timeline to cover all active features
    get_state().get_time_manager().include_all_features(playback_duration=8)

def add_twc_sequence_t2m_callback(ext):
    seq, idx, img = _add_test_sequence_common(ext, PATH_PATTERN, META_DATA_PATH, 't2m')

    # configure and add feature
    img.name = f'TWS Temperature'
    img.colormap = 'afmhot'
    remapping = img.remapping
    remapping['gamma'] = 0.4
    img.remapping = remapping
    _add_test_sequence_common_footer(ext, img)

def add_twc_sequence_ws10_callback(ext):
    seq, idx, img = _add_test_sequence_common(ext, PATH_PATTERN, META_DATA_PATH, 'ws10')

    # configure and add feature
    img.name = f'TWS Wind Speed'
    img.colormap = 'magma'
    remapping = img.remapping
    remapping['gamma'] = 2.0
    img.remapping = remapping
    _add_test_sequence_common_footer(ext, img)


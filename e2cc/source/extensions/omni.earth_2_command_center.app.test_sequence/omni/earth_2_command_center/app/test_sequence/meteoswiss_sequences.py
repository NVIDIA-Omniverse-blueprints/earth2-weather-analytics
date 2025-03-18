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

import numpy as np
import json
import datetime
from pathlib import Path

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence
from omni.earth_2_command_center.app.core.utils import latlong_rect_to_affine_mapping

PATH_PATTERN   = '/tmp/MeteoSwiss/jpeg/500m_cloud_{frame}.jpeg'
#PATH_PATTERN   = '/tmp/test.jpeg'

def add_meteoswiss_sequence_callback(ext):
    # Create Timestamped Sequence
    seq = TimestampedSequence()
    idx = ext.get_next_idx()

    # create a unique url for this sequence
    import uuid
    seq.target_url = f'dynamic://test_sequence_{uuid.uuid4()}'

    import datetime
    frame_skip = 1
    start_frame = 0
    end_frame = 1440
    start_utc = datetime.datetime(2023, 8, 14, 10, 0)
    time_delta = datetime.timedelta(seconds=20)

    to_insert = []
    for i in range(start_frame, end_frame+1, frame_skip):
        cur_utc = start_utc + i*time_delta
        to_insert.append((cur_utc, PATH_PATTERN.format(frame=i)))
    seq.insert_multiple(to_insert)

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()
    img.alpha_sources = [seq.target_url]
    img.time_coverage = seq.time_coverage

    # configure and add feature
    img.name = f'MeteoSwiss Cloud Coverage'
    img.colormap = 'cmo.deep_r'
    img.flip_v = True
    remapping = img.remapping
    remapping['gamma'] = 1.0
    img.remapping = remapping

    from omni.earth_2_command_center.app.core.utils import latlong_rect_to_affine_mapping
    lon_min, lon_max = (4,    14.496)
    lat_min, lat_max = (43.1, 49.596)
    affine_mapping = latlong_rect_to_affine_mapping(
            lon_min, lon_max, lat_min, lat_max,
            is_in_radians=False)
    img.affine = list(affine_mapping.flatten()[0:6])

    # keep references to the sequence and the feature
    ext.add_sequence(seq, img)

    features_api = get_state().get_features_api().add_feature(img)
    # update global timeline to cover all active features
    get_state().get_time_manager().include_all_features(playback_duration=12)

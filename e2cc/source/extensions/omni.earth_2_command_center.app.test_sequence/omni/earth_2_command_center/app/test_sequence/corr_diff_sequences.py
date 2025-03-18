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

def add_corr_diff_callback(ext):
    base_url = carb.settings.get_settings().get_as_string("/exts/omni.earth_2_command_center.app.test_sequence/corr_diff_sample_base")
    path_pattern = base_url + '/corrdiff_test_001/corrdiff_resample_crop_00_wind_magnitude_10_{frame:02d}.jpg'

    # Create Timestamped Sequence
    seq = TimestampedSequence()
    idx = ext.get_next_idx()

    # create a unique url for this sequence
    import uuid
    seq.target_url = f'dynamic://test_sequence_{uuid.uuid4()}'

    import datetime
    start_time = datetime.datetime(year=1990, month=1, day=1)
    # NOTE: That's how the timestamps were stored
    raw = [277824, 277825, 277826, 277827, 277828, 277829, 277830, 277831, 277832, 277833, 277835, 277836, 277837, 277838, 277839, 277840, 277841, 277842, 277843, 277844, 277845, 277846, 277847, 277848, 277849, 277850, 277851, 277852, 277853, 277854, 277855, 277856, 277857, 277859, 277860, 277861, 277862, 277863, 277864]
    timestamps = [start_time+datetime.timedelta(hours=v) for v in raw]
    frame_skip = 1
    start_frame = 0
    end_frame = 38
    to_insert = []
    for i in range(start_frame, end_frame+1, frame_skip):
        cur_utc = timestamps[i]
        to_insert.append((cur_utc, path_pattern.format(frame=i)))
    seq.insert_multiple(to_insert)

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()
    img.sources = [seq.target_url]
    img.alpha_sources = img.sources

    from omni.earth_2_command_center.app.core.utils import latlong_rect_to_affine_mapping, affine_mapping_to_shader_param_value
    lon_min, lon_max = (116.39062500000000, 125.18225097656250)
    lat_min, lat_max = (19.613136291503906, 27.826786041259766)
    affine_mapping = latlong_rect_to_affine_mapping(
            lon_min, lon_max, lat_min, lat_max,
            is_in_radians=False)
    img.affine = affine_mapping_to_shader_param_value(affine_mapping)

    # keep references to the sequence and the feature
    ext.add_sequence(seq, img)
    # configure and add feature
    img.name = f'CorrDiff Wind Magnitude'
    remapping = img.remapping
    remapping['output_gamma'] = 1.5
    img.remapping = remapping
    img.colormap = 'magma'
    img.time_coverage = seq.time_coverage

    features_api = get_state().get_features_api().add_feature(img)
    # update global timeline to cover all active features
    get_state().get_time_manager().include_all_features(playback_duration=4)

def add_era5windmag_callback(ext):
    base_url = carb.settings.get_settings().get_as_string("/exts/omni.earth_2_command_center.app.test_sequence/corr_diff_sample_base")
    path_pattern = base_url + '/era5_wind_mag/wind_mag_{timestamp}.jpg'

    # Create Timestamped Sequence
    seq = TimestampedSequence()
    idx = ext.get_next_idx()

    # create a unique url for this sequence
    import uuid
    seq.target_url = f'dynamic://test_sequence_{uuid.uuid4()}'

    import datetime
    start_time = datetime.datetime(year=2021, month=9, day=11, hour=0, minute=0)
    end_time = datetime.datetime(year=2021, month=9, day=12, hour=16, minute=0)
    timedelta = datetime.timedelta(hours=1)

    timestamps = [start_time+i*timedelta for i in range(int(np.floor((end_time-start_time)/timedelta)))]
    trans_table = str.maketrans({' ':'_', ':':'-'})
    to_insert = []
    for cur_utc in timestamps:
        path = path_pattern.format(timestamp=str(cur_utc).translate(trans_table))
        to_insert.append((cur_utc, path))
    seq.insert_multiple(to_insert)

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()
    img.alpha_sources = [seq.target_url]
    img.sources = img.alpha_sources

    # keep references to the sequence and the feature
    ext.add_sequence(seq, img)
    # configure and add feature
    img.name = f'ERA5 Wind Magnitude'
    remapping = img.remapping
    remapping['output_gamma'] = 1.5
    img.remapping = remapping
    img.colormap = 'magma'
    img.time_coverage = seq.time_coverage

    features_api = get_state().get_features_api().add_feature(img)
    # update global timeline to cover all active features
    get_state().get_time_manager().include_all_features(playback_duration=4)


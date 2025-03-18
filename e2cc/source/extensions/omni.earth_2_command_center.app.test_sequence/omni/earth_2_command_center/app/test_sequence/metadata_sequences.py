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
import dateutil
from pathlib import Path
import re

from pxr import Gf

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence, MosaicTimestampedSequence, DiamondTimestampedSequence
from omni.earth_2_command_center.app.core.utils import latlong_rect_to_affine_mapping, affine_mapping_to_shader_param_value

from omni.kit.window.filepicker import FilePickerDialog

# TODO: we want to support animation of any parameter where it's meaningful
#       if it's set via a time->value mapping, we should generate general timestamped
#       sequence objects, ideally by merging multiple params together
def handle_image_feature(ext, json_path, feature):
    type = feature['type']
    if type != 'Image':
        raise RuntimeError('Expected Image Feature Type')

    # create feature
    features_api = get_state().get_features_api()
    img = features_api.create_image_feature()

    if 'name' in feature:
        img.name = str(feature['name'])

    if 'active' in feature:
        img.active = bool(feature['active'])

    # copy over meta-data
    if 'meta' in feature:
        img.meta = dict(feature['meta'])

    if 'projection' in feature:
        img.projection = str(feature['projection'])

    if 'colormap' in feature:
        img.colormap = feature['colormap']

    if 'colormap_source_channel' in feature:
        img.colormap_source_channel = feature['colormap_source_channel']

    if 'flip_u' in feature:
        img.flip_u = bool(feature['flip_u'])
    if 'flip_v' in feature:
        img.flip_v = bool(feature['flip_v'])

    if 'longitudinal_offset' in feature:
        img.longitudinal_offset = float(feature['longitudinal_offset'])

    # handle 'remapping'
    if 'remapping' in feature:
        r = feature['remapping']
        remapping = img.remapping
        if 'input_min' in r:
            remapping['input_min'] = float(r['input_min'])
        if 'input_max' in r:
            remapping['input_max'] = float(r['input_max'])
        if 'output_min' in r:
            remapping['output_min'] = float(r['output_min'])
        if 'output_max' in r:
            remapping['output_max'] = float(r['output_max'])
        if 'output_gamma' in r:
            remapping['output_gamma'] = float(r['output_gamma'])
        img.remapping = remapping

    # handle 'sources' and 'alpha_sources'
    def handle_sources(name):
        if name in feature:
            # has alpha sources
            sources = feature[name]
            if isinstance(sources, dict):
                # need to create sequence
                # TODO: or this is a split/diamond texture

                # Create Timestamped Sequence
                if img.projection == 'diamond':
                    seq = DiamondTimestampedSequence()
                elif img.projection.startswith("latlong"):
                    if match := re.match(r'latlong_(\d+)_(\d+)', img.projection):
                        long_splits, lat_splits = int(match.group(1)), int(match.group(2))
                        seq = MosaicTimestampedSequence(tileCount=long_splits * lat_splits)
                    else:
                        seq = TimestampedSequence()
                else:
                    seq = TimestampedSequence()

                to_insert = []
                is_mosaic = isinstance(seq, MosaicTimestampedSequence)
                print_timezone_warning = False
                for t,p in sources.items():
                    cur_timestamp = dateutil.parser.isoparse(t)
                    if not cur_timestamp.tzinfo:
                        # assuming UTC timezone
                        if not print_timezone_warning:
                            carb.log_warn('Assuming UTC Timezone for Timestamp with no Timezone information')
                            print_timezone_warning = True
                        cur_timestamp = cur_timestamp.replace(tzinfo=datetime.timezone.utc)

                    if is_mosaic:  # includes diamonds too
                        paths = [str(p_) if Path(p_).is_absolute() else str(Path(json_path).parent / p_) for p_ in p]
                        to_insert.append((cur_timestamp, paths))
                    else:
                        path = str(p) if Path(p).is_absolute() else str(Path(json_path).parent / p)
                        to_insert.append((cur_timestamp, path))
                seq.insert_multiple(to_insert)

                img.time_coverage = seq.time_coverage

                if img.projection == 'diamond':
                    setattr(img, name, seq.target_url)
                    get_state().get_icon_helper().register_diamond_list(img, seq.tex_list())
                elif is_mosaic:
                    setattr(img, name, seq.target_url)
                else:
                    setattr(img, name, [seq.target_url])

                # keep references to the sequence and the feature
                ext.add_sequence(seq, img)
            else:
                if not isinstance(sources, list):
                    sources = [sources]
                sources = [str(p) if (Path(p).is_absolute() or p == '') else str(Path(json_path).parent / p) for p in sources]

                # single image case
                setattr(img, name, sources)

    handle_sources('sources')
    handle_sources('alpha_sources')

    if img.projection.startswith('latlong'):
        # handle affine mappings
        if 'latlon_min' in feature and 'latlon_max' in feature:
            lat_min, lon_min = feature['latlon_min']
            lat_max, lon_max = feature['latlon_max']
            # TODO: check that it's not full globe
            affine_mapping = latlong_rect_to_affine_mapping(
                    lon_min, lon_max, lat_min, lat_max,
                    is_in_radians=False)
            img.affine = affine_mapping_to_shader_param_value(affine_mapping)

    features_api = get_state().get_features_api().add_feature(img)

def handle_curves_feature(ext, json_path, feature):
    type = feature['type']
    if type != 'Curves':
        raise RuntimeError('Expected Curves Feature Type')

    # create feature
    features_api = get_state().get_features_api()
    curve = features_api.create_curves_feature()
    if 'name' in feature:
        curve.name = str(feature['name'])
    if 'active' in feature:
        curve.active = bool(feature['active'])
    if 'meta' in feature:
        curve.meta = dict(feature['meta'])
    if 'projection' in feature:
        curve.projection = str(feature['projection'])
    if 'color' in feature:
        curve.color = Gf.Vec3f(feature['color'])
    if 'periodic' in feature:
        curve.periodic = bool(feature['periodic'])
    if 'width' in feature:
        curve.width = feature['width']
    if 'points' in feature:
        curve.points = np.array(feature['points'])
    if 'points_per_curve' in feature:
        curve.points_per_curve = np.array(feature['points_per_curve'])

    features_api = get_state().get_features_api().add_feature(curve)

def add_from_meta_json(ext, json_path, overrides={}, depth=0, options={}):
    if depth >= 10:
        raise RuntimeError('Max Import Depth Reached')

    #json_path = '/tmp/MeteoSwiss/meta.json'
    with open(json_path, 'r') as file:
        meta_data = json.load(file)

    if 'features' in meta_data:
        features = meta_data['features']
        num_features = len(features)

        # process Image features
        for feature in features:
            feature.update(overrides)
            type = feature['type']
            match type:
                case 'Image':
                    handle_image_feature(ext, json_path, feature)
                case 'Curves':
                    handle_curves_feature(ext, json_path, feature)
                case _:
                    carb.log_error(f'unhandled feature type: {type}')

    if 'imports' in meta_data:
        for cur_import in meta_data['imports']:
            if not 'path' in cur_import:
                raise RuntimeError(f'Invalid import in json: {json_path}')

            # make relative to this path if required
            cur_path = Path(cur_import['path'])
            if not cur_path.is_absolute():
                cur_path = Path(json_path).parent / cur_path

            # get overrides
            if 'overrides' in cur_import:
                overrides = cur_import['overrides']
            else:
                overrides = {}
            # recursion
            add_from_meta_json(ext, str(cur_path), overrides, depth+1)

    if 'options' in meta_data:
        options.update(meta_data['options'])

    # update global timeline to cover all active features
    if depth == 0:
        time_manager = get_state().get_time_manager()

        playback_duration = 10
        if 'playback_duration' in options:
            playback_duration = options['playback_duration']
        time_manager.include_all_features(playback_duration=playback_duration)

        if 'utc_start_time' in options:
            time_manager.utc_start_time = dateutil.parser.isoparse(options['utc_start_time'])
        if 'utc_end_time' in options:
            time_manager.utc_end_time = dateutil.parser.isoparse(options['utc_end_time'])
        if 'utc_time' in options:
            time_manager.utc_time = dateutil.parser.isoparse(options['utc_time'])
        if 'play' in options:
            if bool(options['play']):
                time_manager.get_timeline().play()
            else:
                time_manager.get_timeline().pause()

g_start_directory = None
def add_from_meta_json_callback(ext):
    def on_click(dialog, filename, dirname):
        global g_start_directory
        g_start_directory = dirname
        add_from_meta_json(ext, str(Path(dirname) / Path(filename)))
        dialog.hide()

    dialog = FilePickerDialog(
            'Load from Metadata File',
            apply_button_label = 'Select',
            show_detail_view = False,
            enable_checkpoints = False,
            click_apply_handler = lambda filename, dirname: on_click(dialog, filename, dirname),
            current_directory = g_start_directory)

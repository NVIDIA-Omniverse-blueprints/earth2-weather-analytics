import carb

import numpy as np
import json
import copy
import datetime

from pathlib import Path
import re

from pxr import Gf

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.timestamped_sequence import TimestampedSequence, MosaicTimestampedSequence, DiamondTimestampedSequence, HPXTimestampedSequence
from omni.earth_2_command_center.app.core.utils import latlong_rect_to_affine_mapping, affine_mapping_to_shader_param_value

from omni.kit.window.filepicker import FilePickerDialog

# to avoid having to pull in isodate...
def match_iso_period(period_string):
    '''
    Durations are written as: P[n]Y[n]M[n]DT[n]H[n]M[n]S

    Note: we don't support relative time deltas, so no periods with Years or Months (we allow days though)

    P indicates the period (duration).
    Y = years, M = months, W = weeks, D = days.
    T separates date and time parts.
    H = hours, M = minutes, S = seconds.
    '''

    # pattern for a decimal number
    # we don't allow scientific notation
    num = r'[+-]?(?:\d+(?:\.\d*)?)'
    #pattern = re.compile( rf"""
    #    P                              # always required
    #    (?:({num})Y)?                  # Y[n] Years   (optional)
    #    (?:({num})M)?                  # M[n] Months  (optional)
    #    (?:({num})D)?                  # D[n] Days    (optional)
    #    (?:T                           # separator    (starts time part)
    #    (?:({num})H)?                  # H[n] Hours   (optional)
    #    (?:({num})M)?                  # M[n] Minutes (optional)
    #    (?:({num})S)?                  # S[n] Seconds (optional)
    #    )?                             # ends time part
    #    """, re.VERBOSE)
    pattern = re.compile( rf"""
        P                              # always required
        (?:({num})D)?                  # D[n] Days    (optional)
        (?:T                           # separator    (starts time part)
        (?:({num})H)?                  # H[n] Hours   (optional)
        (?:({num})M)?                  # M[n] Minutes (optional)
        (?:({num})S)?                  # S[n] Seconds (optional)
        )?                             # ends time part
        """, re.VERBOSE)
    match = re.match(pattern, period_string)
    if match is None or 'Y' in period_string or 'W' in period_string:
        carb.log_error(f'Provided period is not valid: \'{period_string}\'. Note, we don\'t support years, months, weeks.')
        return datetime.timedelta()

    values = [float(v) if v is not None else 0 for v in match.groups()]
    dt = datetime.timedelta(
            days=values[0],
            seconds=values[3],
            minutes=values[2],
            hours=values[1])

    return dt

# TODO: we want to support animation of any parameter where it's meaningful
#       if it's set via a time->value mapping, we should generate general timestamped
#       sequence objects, ideally by merging multiple params together
def handle_image_feature(ext, json_path, feature, options=None):
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

    if 'loop' in feature:
        img.loop = feature['loop']

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
    def handle_sources(source_type, options):
        try:
            import dateutil.parser
            date_parser = dateutil.parser.parse
        except ModuleNotFoundError:
            date_parser = datetime.datetime.fromisoformat

        if source_type in feature:
            # has alpha sources
            sources = feature[source_type]
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
                elif img.projection.startswith("goes"):
                    seq = TimestampedSequence()
                elif img.projection.startswith("hpx"):
                    seq = HPXTimestampedSequence()
                else:
                    # TODO: it might be better to error out if it's an unknown
                    # projection and have an explicit 'elif' branch for the known
                    # ones. The following warning will at least make it clear when
                    # we're running into this case
                    carb.log_warn(f'Metadata reading: Projection \'{img.projection}\' handled as a generic timestamped sequence')
                    seq = TimestampedSequence()

                if img.loop:
                    seq.loop = img.loop

                to_insert = []
                # this is true for all MosaicTimestampedSequence subclasses (diamond & hpx, etc.)
                is_mosaic = isinstance(seq, MosaicTimestampedSequence)
                print_timezone_warning = False

                time_shift = datetime.timedelta()
                if 'time_shift' in options:
                    time_shift = options['time_shift'] if isinstance(options['time_shift'], datetime.timedelta) else \
                        match_iso_period(options['time_shift'])
                for t,p in sources.items():
                    cur_timestamp = date_parser(t)+time_shift
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
                    setattr(img, source_type, seq.target_url)
                    get_state().get_icon_helper().register_diamond_list(img, seq.tex_list())
                elif is_mosaic:
                    setattr(img, source_type, seq.target_url)
                else:
                    setattr(img, source_type, [seq.target_url])

                # keep references to the sequence and the feature
                ext.add_sequence(seq, img)
            else:
                if not isinstance(sources, list):
                    sources = [sources]
                sources = [str(p) if (Path(p).is_absolute() or p == '') else str(Path(json_path).parent / p) for p in sources]

                # single image case
                setattr(img, source_type, sources)

    handle_sources('sources', options)
    handle_sources('alpha_sources', options)

    if img.projection.startswith('latlong'):
        # handle affine mappings
        if 'latlon_min' in feature and 'latlon_max' in feature:
            lat_min, lon_min = feature['latlon_min']
            lat_max, lon_max = feature['latlon_max']
            # TODO: check that it's not full globe
            affine_mapping, longitudinal_offset = latlong_rect_to_affine_mapping(
                    lon_min, lon_max, lat_min, lat_max,
                    is_in_radians=False)
            img.affine = affine_mapping_to_shader_param_value(affine_mapping)
            if img.longitudinal_offset is not None:
                img.longitudinal_offset += longitudinal_offset
            else:
                img.longitudinal_offset = longitudinal_offset

    features_api = get_state().get_features_api().add_feature(img)
    return img

def handle_curves_feature(ext, json_path, feature, options=None):
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
    return curve

def add_from_meta_json(ext, json_path, overrides={}, depth=0, options=None):
    if depth >= 10:
        raise RuntimeError('Max Import Depth Reached')

    if options is None:
        options = {}

    #json_path = '/tmp/MeteoSwiss/meta.json'
    with open(json_path, 'r') as file:
        meta_data = json.load(file)

    features_added = []
    if 'options' in meta_data:
        # time shift needs to be combined
        if 'time_shift' in meta_data['options'] and 'time_shift' in options:
            a = meta_data['options']['time_shift']
            b = options['time_shift']
            if not isinstance(a, datetime.timedelta):
                a = match_iso_period(a)
            if not isinstance(b, datetime.timedelta):
                b = match_iso_period(b)
            meta_data['options']['time_shift'] = a+b
        options.update(meta_data['options'])

    if 'features' in meta_data:
        features = meta_data['features']
        num_features = len(features)

        # process Image features
        for feature in features:
            feature.update(overrides)
            type = feature['type']
            match type:
                case 'Image':
                    f = handle_image_feature(ext, json_path, feature, options)
                    features_added.append(f)
                case 'Curves':
                    f = handle_curves_feature(ext, json_path, feature, options)
                    features_added.append(f)
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
            features_added += add_from_meta_json(ext, str(cur_path), overrides, depth+1, copy.deepcopy(options))

    # update global timeline to cover all active features
    if depth == 0:
        time_manager = get_state().get_time_manager()

        try:
            import dateutil.parser
            date_parser = dateutil.parser.parse
        except ModuleNotFoundError:
            date_parser = datetime.datetime.fromisoformat

        start_time = date_parser(options['utc_start_time']) if 'utc_start_time' in options else None
        end_time = date_parser(options['utc_end_time']) if 'utc_end_time' in options else None
        utc_time = date_parser(options['utc_time']) if 'utc_time' in options else None

        # NOTE: we have 2 different cases to differentiate:
        #  Case 1: Time range fully specified (ie start and end is set)
        #  -----------------------------------------------------------
        #  in this case we just set the start and end time to the desired values
        #  and calculate the playback speed directly for that range
        #
        #  Case 2: Time range is not fully specified
        #  -----------------------------------------------------------
        #  in this case, we need to know the time range of the added features.
        #  we then adjust this range in case start/end has been set and then we
        #  are back to case 1, except when we don't have features with time coverage
        #  which would be the static case. then we simply use the start/end time
        #  from the current timeline

        playback_duration = options.get('playback_duration', 10)
        # get current timeline coverage
        time_coverage = time_manager.get_time_coverage(features_added)
        # update with provided start_time if present
        start_time = time_coverage[0] if start_time is None else start_time
        # update with provided end if present
        end_time = time_coverage[1] if end_time is None else end_time
        # sanity check
        if start_time is None or end_time is None:
            carb.log_error(f'could not calculate utc timeline interval')
            return features_added

        # update timeline
        time_manager.set_time_range(start_time, end_time, utc_time, playback_duration)

        # play timeline if requested
        if 'play' in options:
            if bool(options['play']):
                time_manager.get_timeline().play()
            else:
                time_manager.get_timeline().pause()

    return features_added

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

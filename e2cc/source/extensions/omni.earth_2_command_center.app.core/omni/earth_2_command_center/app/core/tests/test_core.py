# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import omni.earth_2_command_center.app.core as core

# for utc time events
from omni.earth_2_command_center.app.core.time_manager import *

import omni.earth_2_command_center.app.core.timestamped_sequence as ts
from omni.earth_2_command_center.app.core.features_api import *
from omni.earth_2_command_center.app.core.sun_motion import *

import omni.kit.test

class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        '''No need for setup work'''

    async def tearDown(self):
        '''No need for teardown work'''

    # ============================================================
    # Core Tests
    # ============================================================
    async def test_core_get_state(self):
        self.assertIsNotNone(core.get_state())

    async def test_core_get_globe_view_event_stream(self):
        self.assertIsNotNone(core.get_state().get_globe_view_event_stream())

    async def test_core_get_features_api(self):
        state = core.get_state()
        self.assertIsNotNone(state.get_features_api())

    # ============================================================
    # Creating Features
    # ============================================================
    async def test_core_create_image_features(self):
        features_api = core.get_state().get_features_api()
        # creating a image feature
        image  = features_api.create_image_feature()
        self.assertIsNotNone(image)

        # check feature id
        self.assertNotEqual(image.id, -1)

        # check feature type
        self.assertEqual(image.type, Image.feature_type)

    async def test_core_create_marker_features(self):
        features_api = core.get_state().get_features_api()
        # creating a marker feature
        marker = features_api.create_marker_feature()
        self.assertIsNotNone(marker)

        # check feature id
        self.assertNotEqual(marker.id, -1)

        # check feature type
        self.assertEqual(marker.type, Marker.feature_type)

    async def test_core_create_volume_features(self):
        features_api = core.get_state().get_features_api()
        # creating a volume feature
        volume = features_api.create_volume_feature()
        self.assertIsNotNone(volume)

        # check feature id
        self.assertNotEqual(volume.id, -1)

        # check feature type
        self.assertEqual(volume.type, Volume.feature_type)

    # ============================================================
    # Managing Features
    # ============================================================
    async def test_core_feature_management(self):
        features_api = core.get_state().get_features_api()
        # getting number of features
        self.assertEqual(features_api.get_num_features(), 0)

        image = features_api.create_image_feature()
        # adding a feature
        features_api.add_feature(image)
        self.assertEqual(features_api.get_num_features(), 1)

        # retrieving features
        self.assertEqual(features_api.get_features()[0], image)

        # make sure we can retrieve the feature by id
        self.assertEqual(features_api.get_feature_by_id(image.id), image)

        # removing a feature
        features_api.remove_feature(image)
        self.assertEqual(features_api.get_num_features(), 0)

        # clearing all features
        features_api.add_feature(image)
        features_api.clear()
        self.assertEqual(features_api.get_num_features(), 0)

        # check filtering by type
        image  = features_api.create_image_feature()
        volume = features_api.create_volume_feature()
        marker = features_api.create_marker_feature()
        features_api.add_feature(image)
        features_api.add_feature(volume)
        features_api.add_feature(marker)

        def check(feature, feature_type):
            features = features_api.get_by_type(feature_type)
            self.assertEqual(features[0], feature)
        for feature, feature_type in [
                (image, Image),
                (volume, Volume),
                (marker, Marker)]:
            check(feature, feature_type)
        self.assertEqual(features_api.get_image_features()[0],  image)
        self.assertEqual(features_api.get_volume_features()[0], volume)
        self.assertEqual(features_api.get_marker_features()[0], marker)

        # check filtering by predicate
        def filter_predicate(feature):
            return feature.type == Volume.feature_type
        self.assertEqual(features_api.get_filtered(filter_predicate)[0],  volume)

        # check adding at specific position
        features_api.clear()
        features_api.add_feature(image)
        features_api.add_feature(volume)
        features_api.add_feature(marker,0)
        self.assertEqual(features_api.get_features()[0], marker)
        features_api.clear()

    async def test_core_feature_reordering(self):
        features_api = core.get_state().get_features_api()
        # getting number of features
        self.assertEqual(features_api.get_num_features(), 0)

        # test permutation list for feature reordering
        features = [features_api.create_image_feature() for i in range(5)]
        for f in features:
            features_api.add_feature(f)
        new_order = [4, 3, 2, 1, 0]
        features_api.reorder_features(new_order)
        self.assertEqual([features[i] for i in new_order], features_api.get_features())

        # check get_feature_pos of each feature
        for idx,f in enumerate(features):
            self.assertEqual(features_api.get_feature_pos(f), new_order[idx])

        # test order mapping reordering
        # this creates a mapping that maps each feature in 'feature' to its own
        # index, basically undoing the reordering from above
        features_api.reorder_features({f:idx for idx,f in enumerate(features)})
        for idx,f in enumerate(features):
            self.assertEqual(features_api.get_feature_pos(f), idx)

        features_api.clear()

    # ============================================================
    # Feature Properties
    # ============================================================
    async def test_core_feature_properties(self):
        feature = Feature()

        # checking feature type
        self.assertEqual(feature.type, Feature.feature_type)

        # checking feature name
        test_name = 'foo'
        feature.name = test_name
        self.assertEqual(feature.name, test_name)

        # checking feature active
        self.assertTrue(feature.active)
        feature.active = False
        self.assertFalse(feature.active)

    async def test_core_feature_properties_time_coverage(self):
        feature = Feature()

        # checking feature time coverage
        self.assertEqual(feature.time_coverage, None)

        from datetime import datetime
        start_time = datetime(1990,1,1)
        end_time = datetime(2000,1,1)
        feature.time_coverage = (start_time, end_time)
        self.assertEqual(feature.time_coverage, (start_time, end_time))

        start_time2 = datetime(1980,1,1)
        end_time2 = datetime(2020,1,1)
        feature.time_coverage_extend_to_include(start_time2, end_time2)
        self.assertEqual(feature.time_coverage, (start_time2, end_time2))

    async def test_core_image_feature_properties(self):
        feature = Image()

        # checking feature type
        self.assertEqual(feature.type, Image.feature_type)

        # checking feature name
        self.assertEqual(feature.projection, 'latlong')
        test_projection = 'foo'
        feature.projection = test_projection
        self.assertEqual(feature.projection, test_projection)

        # checking feature sources
        self.assertEqual(feature.sources, [])
        test_sources = ['foo', 'bar']
        feature.sources = test_sources
        self.assertEqual(feature.sources, test_sources)

        # checking feature alpha_sources
        self.assertEqual(feature.alpha_sources, [])
        test_sources = ['foo', 'bar']
        feature.alpha_sources = test_sources
        self.assertEqual(feature.alpha_sources, test_sources)

        # checking feature colomap
        self.assertIsNone(feature.colormap)
        test_colormap = 'foo'
        feature.colormap = test_colormap
        self.assertEqual(feature.colormap, test_colormap)

        # checking feature colomap_source_channel
        self.assertIsNone(feature.colormap_source_channel)
        test_colormap_source_channel = 'G'
        feature.colormap_source_channel = test_colormap_source_channel
        self.assertEqual(feature.colormap_source_channel, test_colormap_source_channel)

        # checking feature flip_u
        self.assertFalse(feature.flip_u)
        feature.flip_u = True
        self.assertTrue(feature.flip_u)

        # checking feature flip_v
        self.assertFalse(feature.flip_v)
        feature.flip_v = True
        self.assertTrue(feature.flip_v)

        # checking feature longitudinal_offset
        self.assertIsNone(feature.longitudinal_offset)
        feature.longitudinal_offset = 90.0
        self.assertEqual(feature.longitudinal_offset, 90.0)

        # checking feature remapping
        default = {'input_min':0.0, 'input_max':1.0, 'output_min':0.0, 'output_max':1.0, 'output_gamma':1.0}
        self.assertEqual(feature.remapping, default)
        test_remapping = {'min_value': 0, 'max_value': 1}
        feature.remapping = test_remapping
        self.assertEqual(feature.remapping, test_remapping)

    # ============================================================
    # Events
    # ============================================================
    async def test_core_event_stream(self):
        features_api = core.get_state().get_features_api()
        event_stream = features_api.get_event_stream()

        # setup test function that compares the event id and payload to the
        # expected values
        test_type = None
        test_payload = {}
        def on_event(event):
            self.assertEqual(event.type, test_type)
            self.assertEqual(event.payload.get_dict(), test_payload)

        subscription = event_stream.create_subscription_to_pop(on_event)

        image = features_api.create_image_feature()

        # test add feature event
        test_type = FeatureChange.FEATURE_ADD['id']
        base_payload = {'feature_type': image.type, 'id': image.id}
        test_payload = base_payload | {'change': FeatureChange.FEATURE_ADD}
        features_api.add_feature(image)

        image2 = features_api.create_image_feature()
        base_payload = {'feature_type': image.type, 'id': image2.id}
        test_payload = base_payload | {'change': FeatureChange.FEATURE_ADD}
        features_api.add_feature(image2)

        # test property change event
        test_type = FeatureChange.PROPERTY_CHANGE['id']
        base_payload = {'feature_type': image.type, 'id': image.id}
        test_payload = base_payload | {'change': FeatureChange.PROPERTY_CHANGE,
                'property':'name', 'old_value': image.name, 'new_value': 'foo'}
        image.name = 'foo'

        # test reorder feature event
        test_type = FeatureChange.FEATURE_REORDER['id']
        test_payload = {'change': FeatureChange.FEATURE_REORDER, 'permutation': (1, 0)}
        features_api.reorder_features([1, 0])

        # test remove feature event
        test_type = FeatureChange.FEATURE_REMOVE['id']
        test_payload = base_payload | {'change': FeatureChange.FEATURE_REMOVE}
        features_api.remove_feature(image)

        # test clear feature event
        test_type = FeatureChange.FEATURE_CLEAR['id']
        test_payload = {'change': FeatureChange.FEATURE_CLEAR}
        features_api.clear()

        # unsubscribe
        subscription.unsubscribe()

    async def test_utc_time_event_stream(self):
        import datetime
        time_manager = core.get_state().get_time_manager()

        expected_event_type = None
        def on_event(event):
            self.assertEqual(event.type, expected_event_type)

        subscription = time_manager.get_utc_event_stream().create_subscription_to_pop(on_event)

        # utc time change
        expected_event_type = UTC_CURRENT_TIME_CHANGED
        cur_time = time_manager.utc_time
        time_manager.utc_time = cur_time + datetime.timedelta(hours=1)

        # utc start time change
        expected_event_type = UTC_START_TIME_CHANGED
        start_time = time_manager.utc_start_time
        time_manager.utc_start_time = start_time + datetime.timedelta(hours=1)

        # utc end time change
        expected_event_type = UTC_END_TIME_CHANGED
        end_time = time_manager.utc_end_time
        time_manager.utc_end_time = end_time + datetime.timedelta(hours=1)

        # utc per second change
        expected_event_type = UTC_PER_SECOND_CHANGED
        utc_per_second = time_manager.utc_per_second
        time_manager.utc_per_second = utc_per_second + datetime.timedelta(hours=1)

        subscription.unsubscribe()

        # reset
        time_manager.utc_time = cur_time
        time_manager.utc_start_time = start_time
        time_manager.utc_end_time = end_time
        time_manager.utc_per_second = utc_per_second

    # ============================================================
    # Sun Motion tests
    # ============================================================
    async def test_sun_motion(self):
        import datetime

        state = core.get_state()
        features_api = state.get_features_api()
        sun = features_api.create_sun_feature()
        motion = SunMotion(sun)

        # WINTER SOLSTICE....(WINTER) DEC 21 2024 421 AM EST - 0921 UTC
        winter_solstice = datetime.datetime(2024, 12, 21, 9, 21, tzinfo=datetime.timezone.utc)
        self.assertAlmostEqual(motion._get_declination_spencer(winter_solstice), -23.43, places=1)
        self.assertAlmostEqual(motion._get_declination_cooper(winter_solstice), -23.43, places=1)

        # VERNAL EQUINOX.....(SPRING) MAR 20 2026 1046 AM EDT - 1446 UTC
        spring_equinox = datetime.datetime(2026, 3, 20, 14, 46, tzinfo=datetime.timezone.utc)
        self.assertEqual(int(motion._get_declination_spencer(spring_equinox)), 0)
        self.assertEqual(int(motion._get_declination_cooper(spring_equinox)), 0)

        # SUMMER SOLSTICE....(SUMMER) JUN 21 2023 1058 AM EDT - 1458 UTC
        summer_solstice = datetime.datetime(2023, 6, 21, 14, 58)
        self.assertAlmostEqual(motion._get_declination_spencer(summer_solstice), +23.43, places=1)
        self.assertAlmostEqual(motion._get_declination_cooper(summer_solstice), +23.43, places=1)

    # ============================================================
    # TimestampedSequence Tests
    # ============================================================
    async def test_timestamped_sequence_sorted_list_base(self):
        import datetime
        hour = datetime.timedelta(hours=1)

        sorted_list = ts.SortedList()

        # make sure initially empty
        self.assertTrue(sorted_list.empty())

        # insert element
        element = (datetime.datetime(1988, 6, 29, 12, 0, 0), 10)
        sorted_list.insert(element)
        self.assertFalse(sorted_list.empty())

        # find closest with equal lookup
        idx, found = sorted_list.find_closest_smaller_equal(element[0])
        self.assertIsNotNone(found)
        time, value = found
        self.assertEqual(idx, 0)
        self.assertEqual(time, element[0])
        self.assertEqual(value, element[1])

        # find closest with smaller lookup
        idx, found = sorted_list.find_closest_smaller_equal(element[0]-hour)
        self.assertIsNone(idx)
        self.assertIsNone(found)

        # find closest with larger lookup
        idx, found = sorted_list.find_closest_smaller_equal(element[0]+hour)
        self.assertIsNotNone(found)
        time, value = found
        self.assertEqual(idx, 0)
        self.assertEqual(time, element[0])
        self.assertEqual(value, element[1])

        # remove element
        sorted_list.remove(element)
        self.assertTrue(sorted_list.empty())

    async def test_timestamped_sequence_sorted_list_lerp_base(self):
        import datetime
        sorted_list = ts.SortedList()
        hour = datetime.timedelta(hours=1)

        timestamp = datetime.datetime(1988, 6, 29, 12, 0, 0)

        # test with empty list
        lookup = sorted_list.find_lerp_tuple(timestamp)
        self.assertIsNone(lookup)

        # add single element
        element = (timestamp, 100)
        sorted_list.insert(element)

        # lookup at same timestamp
        lookup = sorted_list.find_lerp_tuple(timestamp)
        self.assertIsNotNone(lookup)
        g, A, B = lookup
        self.assertEqual(g, 0)
        self.assertEqual(A, element)
        self.assertEqual(B, element)

        # lookup at earlier timestamp
        lookup = sorted_list.find_lerp_tuple(timestamp-hour)
        self.assertIsNotNone(lookup)
        g, A, B = lookup
        self.assertEqual(g, 0)
        self.assertEqual(A, element)
        self.assertEqual(B, element)

        # lookup at later timestamp
        lookup = sorted_list.find_lerp_tuple(timestamp+hour)
        self.assertIsNotNone(lookup)
        g, A, B = lookup
        self.assertEqual(g, 0)
        self.assertEqual(A, element)
        self.assertEqual(B, element)

        # add second element
        element2 = (timestamp+hour, 200)
        sorted_list.insert(element2)

        # lookup at center timestamp
        lookup = sorted_list.find_lerp_tuple(timestamp + 0.5*hour)
        self.assertIsNotNone(lookup)
        g, A, B = lookup
        self.assertAlmostEqual(g, 0.5)
        self.assertEqual(A, element)
        self.assertEqual(B, element2)

        # use lerp with default function
        lerp_value = sorted_list.lerp(timestamp + 0.5*hour)
        self.assertAlmostEqual(lerp_value, 150)

        # use lerp with custom function
        def my_lerp(g, A, B):
            return (1-g)*A + g*B + 50
        lerp_value = sorted_list.lerp(timestamp + 0.5*hour, my_lerp)
        self.assertAlmostEqual(lerp_value, 150+50)

        # lookup at before timestamp
        lookup = sorted_list.find_lerp_tuple(timestamp - hour)
        self.assertIsNotNone(lookup)
        g, A, B = lookup
        self.assertAlmostEqual(g, 0.0)
        self.assertEqual(A, element)
        self.assertEqual(B, element)

        # lookup at after last timestamp
        lookup = sorted_list.find_lerp_tuple(timestamp + 2*hour)
        self.assertIsNotNone(lookup)
        g, A, B = lookup
        self.assertAlmostEqual(g, 0.0)
        self.assertEqual(A, element2)
        self.assertEqual(B, element2)

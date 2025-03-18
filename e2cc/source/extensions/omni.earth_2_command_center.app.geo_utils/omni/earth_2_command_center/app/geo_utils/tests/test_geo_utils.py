# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from omni.earth_2_command_center.app.geo_utils import get_geo_converter
from omni.earth_2_command_center.app.geo_utils.geo_util import *

import numpy as np

import omni.kit.test

# TODO: Add edge case testing for sphere intersector:
#         - grazing hits
#         - check for numerical instabilities
# Low priority right now as it's only used on the globe but important to make
# it a generic tool

class Test(omni.kit.test.AsyncTestCase):
    async def setUp(self):
        '''No need for setup work'''

    async def tearDown(self):
        '''No need for teardown work'''

    def assertClose(self, a, b, tol = 1e-10):
        self.assertTrue(np.linalg.norm(a-b) <= tol)


    # ============================================================
    # Core Tests
    # ============================================================
    async def test_get_geo_converter(self):
        geo_converter = get_geo_converter()
        self.assertIsNotNone(geo_converter)

    # ============================================================
    # Geo Converter Tests
    # ============================================================
    async def test_geo_converter_up_axis_conversion(self):
        rng = np.random.default_rng(1234)

        # generate random vector within [-100,100]^3 cube
        x, y, z = rng.uniform(-100,100,3)

        self.assertEqual(
                GeoConverter.z_up_to_y_up(*GeoConverter.y_up_to_z_up(x, y ,z)),
                    (x,y,z))

    def sample_conversions(self, geo_converter:GeoConverter, num_samples = 128,
            seed = 1234):
        '''
        helper function to sample random locations and do round-trip conversions
        '''
        rng = np.random.default_rng(seed)

        for i in range(num_samples):
            lon_deg = rng.uniform(-180.0, 180.0)
            lat_deg = rng.uniform(-90.0, 90.0)
            alt     = rng.uniform(0.0, 10000.0)

            x, y, z = geo_converter.lonlatalt_to_xyz(lon_deg, lat_deg, alt)
            lon_deg2, lat_deg2, alt2 = geo_converter.xyz_to_lonlatalt(x, y, z)
            #print(f'{lon_deg}, {lat_deg}, {alt} <-> {lon_deg2}, {lat_deg2}, {alt2}')
            self.assertClose(lon_deg, lon_deg2)
            self.assertClose(lat_deg, lat_deg2)
            self.assertClose(alt,     alt2)

    async def test_geo_converter_modulo_to_range(self):
        modulo_to_range = GeoConverter._modulo_to_range

        # basic sanity check
        self.assertClose(modulo_to_range(0, -180.0, 180.0), 0)

        # check invalid range
        with self.assertRaises(ValueError):
            modulo_to_range(0, +180.0,-180.0)

        # check negative cycles
        self.assertClose(modulo_to_range(-360.0, -180.0, 180.0), 0)
        self.assertClose(modulo_to_range(-450.0, -180.0, 180.0),-90)
        # check positive cycles
        self.assertClose(modulo_to_range(+360.0, -180.0, 180.0), 0)
        self.assertClose(modulo_to_range(+450.0, -180.0, 180.0), 90)


    async def test_geo_converter_lalong_xyz_conversions_z_up(self):
        '''
        round-trip conversion lon,lat,alt -> x,y,z -> lon,lat,alt
        '''
        geo_converter = GeoConverter(up_axis = GeoConverter.UP_AXIS_Z)
        self.sample_conversions(geo_converter)

    async def test_geo_converter_lalong_xyz_conversions_y_up(self):
        '''
        round-trip conversion lon,lat,alt -> x,y,z -> lon,lat,alt
        '''
        geo_converter = GeoConverter(up_axis = GeoConverter.UP_AXIS_Y)
        self.sample_conversions(geo_converter)

    async def test_geo_converter_poles(self):
        '''
        check if poles are handled correctly
        '''

        num_samples = 32
        rng = np.random.default_rng(1234)

        for axis_def, up_vec in [
                (GeoConverter.UP_AXIS_Y, [0,1,0]),
                (GeoConverter.UP_AXIS_Z, [0,0,1])]:
            geo_converter = GeoConverter(up_axis = axis_def, sphere_radius = 1.0)

            for i in range(num_samples):
                lon = rng.uniform(-180.0, 180.0)

                x, y, z = geo_converter.lonlatalt_to_xyz(lon, +90.0, 0)
                self.assertClose(x, up_vec[0])
                self.assertClose(y, up_vec[1])
                self.assertClose(z, up_vec[2])
                x, y, z = geo_converter.lonlatalt_to_xyz(lon, -90.0, 0)
                self.assertClose(x,-up_vec[0])
                self.assertClose(y,-up_vec[1])
                self.assertClose(z,-up_vec[2])

    # ============================================================
    # Sphere Intersector Tests
    # ============================================================
    def sphere_intersection_tester(self, sphere_intersector:SphereIntersector,
            num_samples = 128, seed = 1234, tol = 1e-12):
        '''
        Generates random direction vectors, intersects it with the
        SphereIntersector and verifies the results are within tolerance
        '''
        sphere_origin = sphere_intersector.sphere_center
        sphere_radius = sphere_intersector.sphere_radius

        # generate a random number generator with fixed seed for deterministic
        # results (might change with numpy version changes)
        rng = np.random.default_rng(seed)

        cur_dir = np.array([0.0,0.0,0.0])
        for i in range(num_samples):
            # generate random direction
            cur_dir = rng.uniform(-1,1,3)
            # normalize
            cur_dir /= np.linalg.norm(cur_dir)

            # compute ground truth
            hit_p_truth = -cur_dir*sphere_radius + sphere_origin

            random_length = rng.uniform(.1,9)
            origin = -cur_dir*sphere_radius*10 + sphere_origin
            hit_p = sphere_intersector.intersect(origin, cur_dir*random_length)

            # make sure we indeed did get a hit
            self.assertIsNotNone(hit_p)

            # assert that hit_p and hit_p_truth match (within tolerance)
            self.assertClose(hit_p, hit_p_truth)

    async def test_sphere_intersector_unit_sphere(self):
        sphere_intersector = SphereIntersector(np.array([0.0,0.0,0.0]), 1.0)
        self.sphere_intersection_tester(sphere_intersector)

    async def test_sphere_intersector_nonunit_sphere(self):
        sphere_intersector = SphereIntersector(np.array([0.0,0.0,0.0]), 100.0)
        self.sphere_intersection_tester(sphere_intersector)

    async def test_sphere_intersector_moved_nonunit_sphere(self):
        sphere_intersector = SphereIntersector(np.array([-3.0,4.0,9.0]), 100.0)
        self.sphere_intersection_tester(sphere_intersector)

    # TODO:
    def sphere_intersection_tester_inside(self, sphere_intersector:SphereIntersector,
            num_samples = 128, seed = 1234):
        '''
        Generates random direction vectors inside the sphere, intersects it with the
        SphereIntersector
        '''
        sphere_origin = sphere_intersector.sphere_center
        sphere_radius = sphere_intersector.sphere_radius

        # generate a random number generator with fixed seed for deterministic
        # results (might change with numpy version changes)
        rng = np.random.default_rng(seed)

        cur_dir = np.array([0.0,0.0,0.0])
        for i in range(num_samples):
            # generate random direction
            cur_dir = rng.uniform(-1,1,3)
            # normalize
            cur_dir /= np.linalg.norm(cur_dir)

            # compute ground truth
            hit_p_truth = -cur_dir*sphere_radius + sphere_origin

            # create ray origin within sphere
            random_length = rng.uniform(0,1.0-1e-12)
            origin = -cur_dir*sphere_radius*random_length + sphere_origin
            hit_p = sphere_intersector.intersect(origin, cur_dir)

            # make sure we indeed did get a hit
            self.assertIsNotNone(hit_p)

            # assert that hit_p and hit_p_truth match
            self.assertClose(hit_p, hit_p_truth)

    async def test_sphere_intersector_inside_unit_sphere(self):
        sphere_intersector = SphereIntersector(np.array([0.0,0.0,0.0]), 1.0)
        self.sphere_intersection_tester_inside(sphere_intersector)

    async def test_sphere_intersector_inside_nonunit_sphere(self):
        sphere_intersector = SphereIntersector(np.array([0.0,0.0,0.0]), 100.0)
        self.sphere_intersection_tester_inside(sphere_intersector)

    async def test_sphere_intersector_inside_moved_nonunit_sphere(self):
        sphere_intersector = SphereIntersector(np.array([-3.0,4.0,9.0]), 100.0)
        self.sphere_intersection_tester_inside(sphere_intersector)

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'GeoConverter', 'SphereIntersector' ]
import numpy as np

class GeoConverter:
    UP_AXIS_Z = 'z'
    UP_AXIS_Y = 'y'

    def __init__(self, up_axis: str = UP_AXIS_Z, sphere_lon_offset: float = 0., sphere_radius: float = 100.):
        self._up_axis = up_axis
        self._sphere_lon_offset = sphere_lon_offset
        self._sphere_radius = sphere_radius

    @property
    def sphere_radius(self):
        return self._sphere_radius

    @sphere_radius.setter
    def sphere_radius(self, sphere_radius: float):
        self._sphere_radius = sphere_radius

    def lonlatalt_to_xyz(self, lon_degrees, lat_degrees, altitude):
        # TODO: need to apply modulo after shift
        phi = np.deg2rad(self._modulo_to_range(lon_degrees - self._sphere_lon_offset, -180.0, 180.0))
        theta = np.deg2rad(lat_degrees)

        r = self._sphere_radius + altitude

        x = np.cos(phi) * np.cos(theta) * r
        y = np.sin(phi) * np.cos(theta) * r
        z = np.sin(theta) * r

        # print(f'{lon},{lat},{r} -> {x,y,z}')
        if self._up_axis == self.UP_AXIS_Z:
            return x, y, z
        else:
            return self.z_up_to_y_up(x, y, z)

    def xyz_to_lonlatalt(self, x, y, z):
        if self._up_axis == self.UP_AXIS_Z:
            pass
        else:
            x, y, z = self.y_up_to_z_up(x, y, z)
        r = np.linalg.norm(np.transpose([x, y, z]), axis=-1)
        phi = np.arctan2(y, x)
        theta = np.arcsin(z / r)

        lon_degrees = self._modulo_to_range(np.rad2deg(phi) + self._sphere_lon_offset, -180.0, 180.0)
        lat_degrees = np.rad2deg(theta)
        altitude = r - self._sphere_radius
        return lon_degrees, lat_degrees, altitude

    @staticmethod
    def z_up_to_y_up(x, y, z):
        #return x, z, -y
        return y, z, x

    @staticmethod
    def y_up_to_z_up(x, y, z):
        #return x, -z, y
        return z, x, y

    @staticmethod
    def _modulo_to_range(val, range_min, range_max):
        '''
        Take a value and make sure it's in the required range using modulo
        arithmetics.
        '''
        if range_min >= range_max:
            raise ValueError('Range invalid [{range_min},{range_max}]')

        width = range_max - range_min
        # shift range to start at 0
        val -=  range_min
        # bring to first cycle
        val -= np.floor(val/width)*width
        return val + range_min


class SphereIntersector:
    def __init__(self, sphere_center, sphere_radius):
        self.sphere_center = sphere_center
        self.sphere_radius = sphere_radius

    def intersect(self, ray_origin: np.ndarray, ray_direction: np.ndarray):
        rd2: float = 1. / np.dot(ray_direction, ray_direction)
        CO: np.ndarray = self.sphere_center - ray_origin
        projCO: float = np.dot(CO, ray_direction) * rd2
        perp: np.ndarray = CO - projCO * ray_direction
        l2: float = np.dot(perp, perp)
        r2: float = self.sphere_radius ** 2
        if l2 > r2:
            return None
        td: float = np.sqrt((r2 - l2) * rd2)

        intersection = projCO - td
        return ray_origin + ray_direction * intersection


# XXX: commented this part out as we can't unittest it conveniently and it's
# not used

#if __name__ == "__main__":
#    import matplotlib.pyplot as plt
#
#    fig, (ax0, ax1) = plt.subplots(1, 2)
#
#    def plot_conversion(ax: plt.Axes):
#        n = 19
#
#        lats = np.linspace(-90., 90., n)
#        lons = np.linspace(0., 360., n)
#
#        print(f'lons={lons}')
#        print(f'lats={lats}')
#
#        converter = GeoConverter(sphere_radius=1., up_axis=GeoConverter.UP_AXIS_Y)
#
#        x, y, z = converter.lonlatalt_to_xyz(lons, lats, altitude=2.)
#        print(f'x={x}')
#        print(f'y={y}')
#        print(f'z={z}')
#
#        lons2, lats2, alt = converter.xyz_to_lonlatalt(x, y, z)
#
#        print(f'lons2={lons2}')
#        print(f'lats2={lats2}')
#        print(f'alt={alt}')
#
#        # plt.plot(lons, lons2, label='lon')
#        ax.plot(lons2, x, label='x')
#        ax.plot(lons2, y, label='y')
#        ax.plot(lons2, z, label='z')
#        # plt.plot(lats, lats2, label='lat')
#
#        ax.legend()
#
#    def plot_intersection(ax: plt.Axes):
#        converter = GeoConverter(sphere_radius=1.)
#
#        # ray
#        orig = np.array([-3., 0., 0.])
#        direction = np.array([1., 0.25, 0.25])
#
#        # sphere
#        center = np.array([0.,0.,0.])
#
#        # plot ray
#        ray_points = np.array([orig, orig + direction])
#        ax.plot(ray_points[:,0], ray_points[:,1], label='ray')
#
#        # plot circle
#        lons = np.linspace(0., 360., 33)
#        x, y, z = converter.lonlatalt_to_xyz(lons, 0., altitude=0.)
#        x, y, z = center + [x, y, z]
#        ax.plot(x, y, label=None)
#        ax.set_aspect('equal')
#
#        # intersect
#        intersector = SphereIntersector(center, converter._sphere_radius)
#
#        hit = intersector.intersect(orig, direction)
#
#        print(f'hit: {hit}')
#
#        ax.plot([hit[0]], [hit[1]], 'o', label='intersection')
#
#    plot_conversion(ax0)
#    plot_intersection(ax1)
#
#    plt.show()

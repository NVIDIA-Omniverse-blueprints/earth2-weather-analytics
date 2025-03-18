# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from __future__ import annotations
__all__ = ['GeoUtilsExtension', 'get_geo_converter']

import omni.ext

from .geo_util import GeoConverter

_geo_converter = None

def get_geo_converter() -> GeoConverter:
    global _geo_converter
    return _geo_converter

class GeoUtilsExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._ext_id = ext_id
        # TODO: This doesn't work as this extension is loaded before the stage has been set up
        # we need to move this code out of the datafederation and put it into the globe view
        ## determine up axis
        #viewport_api = self._viewport_window.viewport_api
        #stage = viewport_api.usd_context.get_stage()
        #print(stage)
        #if (UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z):
        #    up_axis = GeoConverter.UP_AXIS_Z
        #else:
        #    up_axis = GeoConverter.UP_AXIS_Y
        # TODO: so for now we hardcode
        up_axis = GeoConverter.UP_AXIS_Z

        global _geo_converter
        _geo_converter = GeoConverter(
            sphere_lon_offset=0.,
            sphere_radius=4950.,
            up_axis=up_axis)

    # XXX: excluded from test coverage as fastShutdown seems to be on during testing
    # and thus it will never on_shutdown
    def on_shutdown(self): # pragma: no cover
        global _geo_converter
        _geo_converter = None

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
__all__ = ['ContinentsOutlineExtension']

import omni.ext

from omni.earth_2_command_center.app.core import get_state

import numpy as np
import asyncio
from pathlib import Path

class ContinentsOutlineExtension(omni.ext.IExt):
    def on_startup(self, ext_id):
        self._ext_id = ext_id
        import omni.kit.app
        ext_folder_path = Path(omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__))
        self._data_path = str(ext_folder_path.joinpath("data"))

        self._feature = None
        asyncio.get_event_loop().create_task(self._populate())

    def on_shutdown(self):
        if self._feature is not None:
            features_api = get_state().get_features_api()
            features_api.remove_feature(self._feature)

    async def _populate(self):
        import omni.usd
        if not omni.usd.get_context().get_stage():
            return

        features_api = get_state().get_features_api()
        self._feature = features_api.create_curves_feature()
        self._feature.name = 'Continents Outline'
        self._feature.active = False

        # get data from json
        curves = []
        import json
        with open(Path(self._data_path)/'coastline.geojson', 'r') as f:
            coastline_geojson = json.load(f)
            for feature in coastline_geojson["features"]:
                lonlat = np.array(feature["geometry"]["coordinates"])
                curves.append(np.column_stack((lonlat[:,1], lonlat[:,0])))
        self._feature.projection = 'latlon'

        # setup topology
        self._feature.points = np.vstack(curves)
        self._feature.points_per_curve = [a.shape[0] for a in curves]
        self._feature.width = 2
        self._feature.color = (1,1,0)
        self._feature.periodic = False

        features_api.add_feature(self._feature)

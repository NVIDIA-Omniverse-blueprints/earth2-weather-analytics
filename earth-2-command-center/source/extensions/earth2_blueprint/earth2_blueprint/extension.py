# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import asyncio
import logging
from pathlib import Path
import datetime
import threading
from pydantic import ValidationError
import copy
from functools import partial
import math

from nv_dfm_core.api import Pipeline, Yield
from nv_dfm_core.session import Session, Job
from nv_dfm_core.exec import Frame
from nv_dfm_lib_common.schemas import TextureFile, TextureFileList

import carb
import carb.settings
import omni.usd
import omni.kit.async_engine as async_engine
import omni.kit.app as kit_app

from omni.earth_2_command_center.app.core import get_state
from omni.earth_2_command_center.app.core.features.light import Sun
from omni.earth_2_command_center.app.core.utils import install_python_dependency
from omni.earth_2_command_center.app.dfm import get_dfm
from omni.earth_2_command_center.app.dfm.scheduler import *

from nv_dfm_core.api import Pipeline, Yield, PlaceParam

from .feature_wrapper import *
from .main_window import *

# example pipeline
def build_pipeline(site):
    from federation.fed.api.dataloader import LoadGfsEra5Data, LoadCmip6Data
    from federation.fed.api.xarray import ConvertToUint8, RenderUint8ToImages

    with Pipeline() as pipeline:
        gfs_data = LoadGfsEra5Data(
            site=site,
            variables=PlaceParam(place="load_variables"),
            selection=PlaceParam(place="selection"),
            invalidate_cache=False
        )
        convert_to_uint8 = ConvertToUint8(
            site=site,
            data=gfs_data,
            time_dimension="time",
            xydims=["lon", "lat"],
            min_value=PlaceParam(place="min_value"),
            max_value=PlaceParam(place="max_value"),
        )
        render = RenderUint8ToImages(
            site=site,
            data=convert_to_uint8,
            variable=PlaceParam(place="variable"),
            xydims=["lon", "lat"],
            time_dimension="time",
            format="jpeg",
            quality=92,
            return_image_data=True,
        )
        Yield(value=render)

    input_params = {
            'load_variables': ['t2m'],
            'variable': 't2m',
            'selection': {"time": "1988-06-29"},
            'min_value': 273.15-10,
            'max_value': 273.15+40,
            }

    return pipeline, input_params

def build_blueprint_pipeline(site, output_variables=None):
    from federation.fed.api.dataloader import LoadGfsEra5Data, LoadCmip6Data
    from federation.fed.api.xarray import ConvertToUint8, RenderUint8ToImages
    from federation.fed.api.sfno import SfnoPrognostic
    SFNO_VARIABLES = [
        "u10m", "v10m", "u100m", "v100m", "t2m", "sp", "msl", "tcwv",
        "u50", "u100", "u150", "u200", "u250", "u300", "u400", "u500",
        "u600", "u700", "u850", "u925", "u1000",
        "v50", "v100", "v150", "v200", "v250", "v300", "v400", "v500",
        "v600", "v700", "v850", "v925", "v1000",
        "z50", "z100", "z150", "z200", "z250", "z300", "z400", "z500",
        "z600", "z700", "z850", "z925", "z1000",
        "t50", "t100", "t150", "t200", "t250", "t300", "t400", "t500",
        "t600", "t700", "t850", "t925", "t1000",
        "q50", "q100", "q150", "q200", "q250", "q300", "q400", "q500",
        "q600", "q700", "q850", "q925", "q1000",
    ]
    n_steps = 30

    if output_variables is None:
        output_variables = ['t2m', 'msl', 'tcwv']

    yield_places = {}
    with Pipeline() as pipeline:
        gfs_data = LoadGfsEra5Data(
                site=site,
                variables=SFNO_VARIABLES,
                selection=PlaceParam(place="selection"),
                invalidate_cache=False
                )
        forecast = SfnoPrognostic(
                site=site,
                dataset=gfs_data,
                n_steps=PlaceParam(place="n_steps"),
                device=PlaceParam(place="device"),
                )
        for var in output_variables:
            uint8 = ConvertToUint8(
                    site=site,
                    data=forecast,
                    time_dimension="time",
                    xydims=["lon", "lat"],
                    min_value=PlaceParam(place=f"{var}_min_value"),
                    max_value=PlaceParam(place=f"{var}_max_value"),
                    )
            images = RenderUint8ToImages(
                    site=site,
                    data=uint8,
                    variable=var,
                    xydims=["lon", "lat"],
                    time_dimension="time",
                    format="jpeg", quality=92,
                    return_image_data=True
                    )
            place = f'blueprint_{var}'
            Yield(value=images, place=place)
            yield_places[var] = place

    input_params = {
            'n_steps': 6,
            'device': 'cuda',
            'selection': {"time": "2022-01-01"},
            }


    return pipeline, input_params, yield_places

class PipelineRunner:
    def __init__(self,
                 flare_workspace,
                 job_workspace,
                 admin_package,
                 user,
                 site = 'client1',
                 *args, **kwargs):
        self._flare_workspace = flare_workspace
        self._job_workspace = job_workspace
        self._admin_package = admin_package
        self._user = user
        self._site = site

        self._image_features = {}
        self._jobs = []

    def _yield_callback(self, image_feature, _from_site: str, _node: int | str | None,
                        _frame: Frame, target_place: str, data: object) -> None:
        carb.log_info(f'yield callback: {type(data)}, target_place: {target_place}')
        if isinstance(data, TextureFileList) or hasattr(data, 'texture_files'):
            #carb.log_warn(f'data: {data}')
            texture_files = getattr(data, 'texture_files', [])
            for j,tf in enumerate(texture_files):
                import base64
                data = base64.b64decode(tf.base64_image_data)
                timestamp = datetime.datetime.fromisoformat(tf.timestamp)
                image_feature.add_image(timestamp, data)

    def run_sync(self, variables, *args, **kwargs):
        return asyncio.run(self.run_async(*args, **kwargs))

    def _new_session(self):
        from federation.fed.runtime.homesite import get_session
        return get_session(
            target="flare",
            user=self._user,
            flare_workspace=self._flare_workspace,
            job_workspace=self._job_workspace,
            admin_package=self._admin_package)

    async def run_async(self, variables, *args, **kwargs):
        self.cancel()
        try:
            if not variables:
                carb.log_warn('no output variables selected')
                return
            self._pipeline, self._input_params, self._yield_places = \
                    build_blueprint_pipeline(site=self._site,
                                             output_variables=list(variables.keys()))

            time_manager = get_state().get_time_manager()
            time_manager.get_timeline().pause()

            # prepare input params
            input_params = kwargs.get('input_params')
            input_params = self._input_params if not input_params else self._input_params | input_params

            n_steps = input_params['n_steps']
            utc_start = datetime.datetime.fromisoformat(input_params['selection']['time'])
            utc_delta = datetime.timedelta(hours=6)
            # make start-end be a multiple of 24hrs too make the sun movement loopable
            def round_to_full_day(start, end):
                diff_seconds = (end-start).total_seconds()
                diff_days = diff_seconds/(60*60*24)
                return start + datetime.timedelta(days=math.ceil(diff_days))
            utc_end = round_to_full_day(utc_start, utc_start + (n_steps+1)*utc_delta)

            time_manager.utc_start_time = utc_start
            time_manager.utc_end_time = utc_end
            # playback speed is 1 day/second of playback
            time_manager.utc_per_second = datetime.timedelta(days=1)

            # make sure we have an image feature wrapper for all variables
            for varname,var in variables.items():
                if varname not in self._image_features:
                    self._image_features[varname] = ImageFeatureWrapper()
                wrapper = self._image_features[varname]
                wrapper.clear_images()
                wrapper.feature.name = var['name']
                wrapper.feature.colormap = var['colormap'] if var['colormap'] != 'greyscale' else None
                wrapper.feature.remapping |= {'output_gamma':var['output_gamma']}
                # TODO: check how this is serialized in carb.events
                wrapper.feature.time_coverage = (utc_start, utc_end)
                wrapper.visible = False
                wrapper.add()

            self._jobs.append(DFMSchedulerTask(
                session=self._new_session(), pipeline=self._pipeline, site=self._site,
                place_callbacks={place:partial(self._yield_callback, self._image_features[var])
                                 for var,place in self._yield_places.items()},
                timeout=900).schedule(input_params=input_params))

            await asyncio.gather(*[j.wait() for j in self._jobs])

            time_manager.get_timeline().play()
            # make the first feature visible
            if variables:
                self._image_features[list(variables.keys())[0]].visible = True
            # turn off the sun to avoid 'disco ball' visualization
            for f in get_state().get_features_api().get_light_features():
                if isinstance(f, Sun):
                    f.active = False

            carb.log_info(f'done...')

        except Exception as e:
            import traceback
            traceback.print_exc()
        finally:
            self.cancel()


    def cancel(self):
        for j in self._jobs:
            if j.running():
                j.cancel()
        self._jobs = []

    def __del__(self):
        self._image_feature = None
        self.cancel()

_ext = None
def get_ext():
    global _ext
    return _ext

class Earth2BlueprintExtension(omni.ext.IExt):
    def on_startup(self, _ext_id: str):
        global _ext
        _ext = self

        settings = carb.settings.get_settings()
        flare_workspace = Path(settings.get('exts/earth2_blueprint/flare_workspace'))
        job_workspace = Path(settings.get('exts/earth2_blueprint/job_workspace'))
        admin_package = Path(settings.get('exts/earth2_blueprint/admin_package'))
        user = settings.get('exts/earth2_blueprint/user')

        self._main_window = None
        self._pipeline_runner = PipelineRunner(
                flare_workspace=flare_workspace,
                job_workspace=job_workspace,
                admin_package=admin_package,
                user=user)
        async_engine.run_coroutine(self.delay_setup())

    def get_pieline_runner(self):
        return self._pipeline_runner

    async def delay_setup(self, delay=2):
        # NOTE: the delay is to wait until the layout has been applied
        await asyncio.sleep(delay)
        self._main_window = MainWindow('Earth-2 Blueprint - SFNO DFM Pipeline',
                                       # align it with the toolbar
                                       position_x = 90, position_y = 56,
                                       width=0, height=0)

    def on_shutdown(self):
        global _ext
        _ext = None

        if self._main_window:
            self._main_window.destroy()
            self._main_window = None
        self._pipeline_runner = None

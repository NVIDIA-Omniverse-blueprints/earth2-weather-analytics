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
from omni.earth_2_command_center.app.core.utils import install_python_dependency
from omni.earth_2_command_center.app.dfm import get_dfm
from omni.earth_2_command_center.app.dfm.scheduler import *

from nv_dfm_core.api import Pipeline, Yield, PlaceParam

from .feature_wrapper import *
from .main_window import *

DEFAULT_POC_FLARE_WORKSPACE = Path("/home/phadorn/workspace/nvidia/earth-2-command-center/blueprint/workspace/earth2_poc/")
DEFAULT_POC_JOB_WORKSPACE = Path("/tmp/job_workspace")
DEFAULT_POC_ADMIN_PACKAGE = Path(
    "/home/phadorn/workspace/nvidia/earth-2-command-center/blueprint/workspace/earth2_poc/federation/prod_00/homesite@earth2.nvidia.com"
)
DEFAULT_POC_USER = "homesite@earth2.nvidia.com"

# example pipeline
def build_pipeline(site):
    from federation.fed.api.dataloader import LoadGfsEra5Data
    from federation.fed.api.xarray import ConvertToUint8, RenderUint8ToImages

    with Pipeline() as pipeline:
        gfs_data = LoadGfsEra5Data(
            site=site,
            variables=PlaceParam(place="load_variables"),
            selection=PlaceParam(place="selection"),
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

#def build_cbottle_pipeline(site):
#    from federation.fed.api.earth2 import CBottleTropicalCycloneGuidance, CbottleVideo
#
#    places = []
#    lat_coords = [15.0, 16.0, 17.0]
#    lon_coords = [-60.0, -61.0, -62.0]
#    seed=1337
#    sampler_steps=18
#    sigma_max=200.0
#    device="cuda"
#
#    with Pipeline() as pipeline:
#        tc = CBottleTropicalCycloneGuidance(
#            site=site,
#            lat_coords=lat_coords,
#            lon_coords=lon_coords,
#            times=[date],
#            sampler_steps=sampler_steps,
#            sigma_max=sigma_max,
#            seed=seed,
#            device=device,
#            lat_lon=True,
#        )
#        video = CbottleVideo(
#            site=site,
#            dataset=tc,
#            n_steps=num_timesteps,
#            seed=seed,
#            device="cuda",
#            lat_lon=True,
#        )
#        tex = ConvertToUint8(
#            site=site,
#            data=video,
#            time_dimension="time",
#            xydims=["lon", "lat"],
#            min_value=273.15-20,
#            max_value=273.15+40,
#        )
#        render_uint8_to_images = RenderUint8ToImages(
#            site=site,
#            data=tex,
#            variable='t2m',
#            xydims=["lon", "lat"],
#            time_dimension="time",
#            additional_meta_data=json.dumps({"variable": 't2m', "texture": texture}),
#            return_meta_data=True,
#            return_image_data=True,
#            format="jpeg", quality=92,
#        )
#        place = f"yield_foo"
#        places.append(place)
#        Yield(value=render_uint8_to_images, place=place)
#
#    return pipeline

class PipelineRunner:
    def __init__(self, *args, **kwargs):
        self._image_feature = ImageFeatureWrapper(
                name='DFM Test Layer', colormap='afmhot')
        self._jobs = []
        self._site = 'client1'
        self._pipeline, self._input_params = build_pipeline(site=self._site)

    def _yield_callback(self, _from_site: str, _node: int | str | None,
                        _frame: Frame, target_place: str, data: object) -> None:
        if isinstance(data, TextureFileList) or hasattr(data, 'texture_files'):
            # adding feature in case it's not already added (safe to call multiple times)
            self._image_feature.add()
            carb.log_warn(f'yield callback: {data}')
            texture_files = getattr(data, 'texture_files', [])
            for j,tf in enumerate(texture_files):
                import base64
                data = base64.b64decode(tf.base64_image_data)
                timestamp = datetime.datetime.fromisoformat(tf.timestamp)
                self._image_feature.add_image(timestamp, data)

    def run_sync(self):
        return asyncio.run(self.run_async())

    async def run_async(self):
        self.cancel()
        try:
            from federation.fed.runtime.homesite import get_session

            def new_session():
                return get_session(
                        target="flare",
                        user=DEFAULT_POC_USER,
                        flare_workspace=DEFAULT_POC_FLARE_WORKSPACE,
                        job_workspace=DEFAULT_POC_JOB_WORKSPACE,
                        admin_package=DEFAULT_POC_ADMIN_PACKAGE)

            num_steps = 12
            utc_start = datetime.datetime(2021, 6, 1, 12, 0)
            utc_delta = datetime.timedelta(hours=6)
            utc_end = utc_start + num_steps*utc_delta
            time_manager = get_state().get_time_manager()
            time_manager.utc_start_time = utc_start
            time_manager.utc_end_time = utc_end
            time_manager.utc_per_second = utc_delta*2
            time_manager.get_timeline().play()
            self._image_feature.feature.time_coverage = (utc_start, utc_end)

            # prepare input params
            input_params_list = []
            for i in range(num_steps):
                input_params = copy.deepcopy(self._input_params)
                input_params['selection'] = {"time": (utc_start + i*utc_delta).isoformat()}
                input_params_list.append(input_params)

            use_single_execute = False
            if use_single_execute:
                self._jobs.append(DFMSchedulerTask(
                    session=new_session(), pipeline=self._pipeline, site=self._site,
                    yield_callback=self._yield_callback,
                    timeout=300).schedule(input_params=input_params_list))
            else:
                for cur_input_params in input_params_list:
                    self._jobs.append(DFMSchedulerTask(
                        session=new_session(), pipeline=self._pipeline, site=self._site,
                        yield_callback=self._yield_callback,
                        timeout=300).schedule(input_params=cur_input_params))

            carb.log_warn(f'Waiting for jobs to finish...')
            await asyncio.gather(*[j.wait() for j in self._jobs])

            carb.log_warn(f'done...')

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

        self._main_window = None
        self._pipeline_runner = PipelineRunner()
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

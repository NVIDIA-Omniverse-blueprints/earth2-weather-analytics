# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

__all__ = ['DfmExtension', 'get_dfm']

import carb
import carb.settings
import omni.kit.async_engine
import omni.kit.app as kit_app

from multiprocessing import get_start_method, set_start_method, get_context

_dfm = None
def get_dfm():
    global _dfm
    return _dfm

class DfmExtension(omni.ext.IExt):
    def on_startup(self, _ext_id: str):
        global _dfm
        _dfm = self

        self._scheduler = None
        self._dfm_supported = self._check_support()
        self.initialize()

    def _check_support(self):
        import os
        if os.name == 'nt':
            return False
        return True

    @property
    def supported_platform(self):
        return self._dfm_supported

    def get_scheduler(self):
        if self._scheduler is None:
            carb.log_error('DFM not supported on this platform')
        return self._scheduler

    def schedule(self, *args, **kwargs):
        if self._scheduler is None:
            carb.log_error('DFM not supported on this platform')
            return None
        return self._scheduler.schedule(*args, **kwargs)

    def initialize(self):
        self._prepare_environment(print_versions=False)
        if self.supported_platform:
            from .scheduler import DFMScheduler
            self._scheduler = DFMScheduler()

        # set the python executable to the one in the kit root
        manager = kit_app.get_app().get_extension_manager()
        path = manager.get_extension_path_by_module("omni.kit.async_engine")
        import os
        kit_root = os.path.abspath(os.path.join(path, "..", ".."))
        if os.name == "nt":
            python_exe = os.path.join(kit_root, "kit", "python", "python.exe")
        else:
            python_exe = os.path.join(kit_root, "kit", "python", "bin", "python3")
        ctx = get_context("spawn")
        ctx.set_executable(python_exe)

        settings = carb.settings.get_settings()
        deployment_mode = settings.get('/exts/omni.earth_2_command_center.app.dfm/dfm/deployment')
        if deployment_mode == 'local':
            if get_start_method(allow_none=True) is None:
                set_start_method("spawn")
        else:
            # NOTE: with POC mode, spawn start methods leads to broken pipes
            # set to spawn to avoid issues with multiprocessing and CUDA
            pass

    def _print_versions(self):
        import platform
        import pydantic
        import sys, os

        appendum = ""
        if self.supported_platform:
            import nv_dfm_core, nv_dfm_lib_common
            appendum = f"""\tDFM Core version: {nv_dfm_core.__version__}
            \tDFM Lib Common version: {nv_dfm_lib_common.__version__}
            """

        carb.log_warn(f"""
        DFM Version Check:
            \tPython version: {platform.python_version()}
            \tPython version: {sys.version}
            \tVersion info: {sys.version_info}
            \tPython executable: {sys.executable}
            \tPydantic version: {pydantic.__version__}
            {appendum}
            """)

    def _prepare_environment(self, print_versions=False):
        if print_versions:
            self._print_versions()


    def on_shutdown(self):
        self._scheduler = None
        global _dfm
        _dfm = None


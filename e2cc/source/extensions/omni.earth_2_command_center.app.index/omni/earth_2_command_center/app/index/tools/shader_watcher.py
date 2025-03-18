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
import os.path
from typing import Any, Callable, Optional

import carb
import omni.kit.app
import watchdog.events
import watchdog.observers
import watchdog.observers.api
from omni.kit import async_engine
from pxr import Usd, UsdShade

from ..settings import WATCH_SHADERS


class ShaderWatcher(watchdog.events.FileSystemEventHandler):
    _observer: watchdog.observers.api.BaseObserver
    _watches: dict[str, tuple[watchdog.observers.api.ObservedWatch, dict[UsdShade.Shader, Callable[[str], str]] | None]]

    def __init__(self, eventloop: asyncio.AbstractEventLoop):
        self._watches = {}
        self._observer = watchdog.observers.Observer()
        self._observer.start()
        self._eventloop = eventloop

    def __del__(self):
        self.dispose()

    def dispose(self):
        self._observer.unschedule_all()
        self._observer.stop()
        self._watches.clear()

    def add_watch(self, path: str, shader: UsdShade.Shader, transform: Optional[Callable[[str], str]] = None):
        path = os.path.abspath(path)
        cbs = self._watches.get(path, (self._observer.schedule(self, path), {}))
        cbs[1][shader] = transform
        self._watches[path] = cbs

    def remove_watch(self, path: str, prim: Usd.Prim):
        path = os.path.abspath(path)
        cbs = self._watches[path]
        self._observer.unschedule(cbs[0])
        del self._watches[path]

    def on_modified(self, event: watchdog.events.FileModifiedEvent | watchdog.events.DirModifiedEvent):
        if event and event.event_type == watchdog.events.EVENT_TYPE_MODIFIED and not event.is_directory:
            watch = self._watches[event.src_path][1]
            expired: list[UsdShade.Shader] = []
            for shader, cb in watch.items():
                if shader.GetPrim().IsValid():
                    carb.log_info(f"Schedule shader reload for {event.src_path}")
                    if shader.GetImplementationSource() == "sourceAsset":
                        if cb is not None:
                            carb.log_warning(
                                f"Filter callback is not support when watching a source asset, only with a source code."
                            )
                        sourceasset = shader.GetSourceAsset("xac")

                        async def set_source_asset():
                            carb.log_info(f"Reloading shader from source {sourceasset}")
                            if shader.GetPrim().HasAttribute("info:xac:sourceAsset"):
                                shader.GetPrim().GetAttribute("info:xac:sourceAsset").Clear()  # force an update
                                await omni.kit.app.get_app().next_update_async()
                            shader.SetSourceAsset(sourceasset, "xac")
                            await omni.kit.app.get_app().next_update_async()

                        # async_engine.run_coroutine(set_source_asset())
                        asyncio.run_coroutine_threadsafe(set_source_asset(), self._eventloop)
                    else:
                        with open(event.src_path, "r") as fp:
                            shader_code = fp.read()
                            if cb is not None:
                                shader_code = cb(shader_code)

                        async def set_source_code():
                            carb.log_info("Reloading shader from source code")
                            if shader.GetPrim().HasAttribute("info:xac:sourceCode"):
                                shader.GetPrim().GetAttribute("info:xac:sourceCode").Clear()  # force an update
                                await omni.kit.app.get_app().next_update_async()
                            shader.SetSourceCode(shader_code, "xac")
                            await omni.kit.app.get_app().next_update_async()

                        # async_engine.run_coroutine(set_source_code())
                        asyncio.run_coroutine_threadsafe(set_source_code(), self._eventloop)
                else:
                    expired.append(shader)

            for ex in expired:
                del watch[ex]


shader_watcher: ShaderWatcher | None = ShaderWatcher(asyncio.get_event_loop()) if WATCH_SHADERS else None

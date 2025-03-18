# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from os.path import splitext
from tempfile import NamedTemporaryFile
from typing import IO, Any, Callable, cast

import carb
import watchdog.events
import watchdog.observers
import watchdog.observers.api
from carb.settings import get_settings
from jinja2 import Template

from ..settings import WATCH_SHADERS


class CodeGen(watchdog.events.FileSystemEventHandler):
    _template_path: str
    _generatedfile: IO[str]
    _variables: dict[str, Any]

    _observer: watchdog.observers.api.BaseObserver | None = watchdog.observers.Observer() if WATCH_SHADERS else None
    _watch_count: int = 0
    _watch: watchdog.observers.api.ObservedWatch | None

    def __init__(self, templatefile_path: str, outputfile_anno: str, on_render: Callable[[str], None] | None = None):
        assert templatefile_path.endswith(".j2")
        self._template_path = templatefile_path
        output_extension = splitext(splitext(templatefile_path)[0])[1]  # get the extension minus feil final.j2
        self._generatedfile = NamedTemporaryFile(
            mode="t+r", encoding="utf-8", suffix=f"{outputfile_anno}{output_extension}"
        )
        self._variables = {}
        self._on_render = on_render

        if self._observer is not None:
            if CodeGen._watch_count == 0:
                CodeGen._observer.start()
            CodeGen._watch_count += 1

            self._watch = CodeGen._observer.schedule(self, templatefile_path)
            carb.log_info(f"Watching codegen source file {templatefile_path}. Generating to {self._generatedfile}")

    def __del__(self):
        self.dispose()

    def dispose(self):
        if self._observer is not None:
            if self._watch is not None:
                carb.log_info(
                    f"Stop Watching codegen source file {self._template_path}\nWas generating to {self._generatedfile.name}"
                )
                CodeGen._observer.unschedule(self._watch)
                self._watch = None
            CodeGen._watch_count -= 1
            if CodeGen._watch_count == 0:
                self._observer.stop()

    @property
    def generate_file_path(self):
        return cast(str, self._generatedfile.name)

    def update_codegen_dict(self, variables: dict[str, Any]):
        self._variables = variables
        self._render()

    def on_modified(self, event: watchdog.events.FileModifiedEvent | watchdog.events.DirModifiedEvent):
        if event and event.event_type == watchdog.events.EVENT_TYPE_MODIFIED and not event.is_directory:
            if event.src_path == self._template_path:
                self._render()

    def _render(self):
        with open(self._template_path, "rt") as f:
            template = Template(f.read())
        assert template

        newcontent = template.render(**self._variables)
        try:
            self._generatedfile.seek(0)
            currentcontent = self._generatedfile.read()

            if currentcontent == newcontent:
                return
        except:
            pass

        carb.log_info(f"Generating {self._generatedfile.name} from {self._template_path}")
        try:
            self._generatedfile.seek(0)
            self._generatedfile.truncate()
            self._generatedfile.write(newcontent)
        except Exception as e:
            carb.log_error(f"Failed rendering template file {self._template_path}:\n{e}")

        if self._on_render:
            self._on_render(self._generatedfile.name)

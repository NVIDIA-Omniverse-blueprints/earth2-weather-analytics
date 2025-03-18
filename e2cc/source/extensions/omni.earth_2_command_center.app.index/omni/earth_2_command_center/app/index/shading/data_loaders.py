# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from abc import ABC
from datetime import datetime, timedelta
from tempfile import NamedTemporaryFile
from typing import IO

from pxr import Sdf, Usd, UsdShade


class DataLoader(ABC):
    pass


class OpenVDBLoader(DataLoader):
    pass


class NanoVDBLoader:
    _stage: Usd.Stage
    _data_loader: UsdShade.Shader
    _series_tmpfile: IO[str] | None

    def __init__(
        self, stage: Usd.Stage, dataloader_path: Sdf.Path, files: list[str], series: tuple[datetime, datetime] | None
    ):
        assert files

        self._stage = stage
        self._data_loader = UsdShade.Shader.Define(stage, dataloader_path)

        # define data loader attributes.
        data_loader_prim = self._data_loader.GetPrim()
        data_loader_prim.CreateAttribute("info:id", Sdf.ValueTypeNames.Token, variability=Sdf.VariabilityUniform).Set(
            "nv::index::plugin::openvdb_integration::vdb_interface_factory.NanoVDB_GDS_update_task"
        )
        data_loader_prim.CreateAttribute(
            "info:implementationSource", Sdf.ValueTypeNames.Token, variability=Sdf.VariabilityUniform
        ).Set("id")
        self._data_loader.CreateInput("compute_mode", Sdf.ValueTypeNames.String).Set("gds_io")
        self._data_loader.CreateInput("enabled", Sdf.ValueTypeNames.Bool).Set(True)
        self._data_loader.CreateInput("is_verbose", Sdf.ValueTypeNames.Bool).Set(True)

        if series is not None:
            # We have a file series, let's create a temporary timestep list file.
            self._series_tmpfile = NamedTemporaryFile(
                mode="t+r", encoding="utf-8", suffix=".timesteps.txt"
            )  # , newline='\n')
            self._series_tmpfile.writelines(s + "\n" for s in files)
            self._series_tmpfile.flush()

            self._data_loader.CreateInput("timestamp_list_file", Sdf.ValueTypeNames.String).Set(
                self._series_tmpfile.name
            )
            self._data_loader.CreateInput("attrib_file_00", Sdf.ValueTypeNames.Token).Set("%T")
            self._data_loader.CreateInput("timestep_offset", Sdf.ValueTypeNames.Int).Set(0)
            self._data_loader.CreateInput("timestep_stride", Sdf.ValueTypeNames.Int).Set(1)
        else:
            self._data_loader.CreateInput("attrib_file_00", Sdf.ValueTypeNames.Token).Set(files[0])

        self._data_loader.CreateOutput("compute", Sdf.ValueTypeNames.Token)

    def __del__(self):
        self.dispose()

    def dispose(self):
        self._stage.RemovePrim(self._data_loader.GetPrim().GetPath())

    def get_usd_data_loader(self):
        return self._data_loader

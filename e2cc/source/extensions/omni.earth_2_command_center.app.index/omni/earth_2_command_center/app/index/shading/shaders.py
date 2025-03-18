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
from dataclasses import dataclass

from pxr import Sdf, Usd, UsdShade, Vt

from ..core import Colormap
from ..settings import PROJECTION_SETTINGS, SHADERS_PATH
from ..tools.shader_watcher import shader_watcher
from ..typing import RangeF1D, ShaderSamplerType
from .codegen import CodeGen
from .volumes import RegularVolume, SphericalProjectionVolume


@dataclass
class FieldDescriptor:
    name: str
    volume: RegularVolume
    lat_range: RangeF1D
    lon_range: RangeF1D
    alt_range: RangeF1D
    channel_index: int
    sampler_type: ShaderSamplerType
    zrectilinear_mapping: list[float] | None = None


class VolumeShader(ABC):
    _stage: Usd.Stage
    _shader: UsdShade.Shader

    def __init__(self, stage: Usd.Stage, shaderpath: Sdf.Path, **kwargs):
        self._stage = stage
        self._shader = UsdShade.Shader.Define(stage, shaderpath)
        self._shader.CreateOutput("volume", Sdf.ValueTypeNames.Token)
        if "sourceasset" in kwargs:
            if "sourcefilter" in kwargs:
                with open(kwargs["sourceasset"], "r") as f:
                    sourcecode = kwargs["sourcefilter"](f.read())
                    self._shader.SetSourceCode(sourcecode, "xac")
            else:
                self._shader.SetSourceAsset(kwargs["sourceasset"], "xac")

            if shader_watcher:
                shader_watcher.add_watch(kwargs["sourceasset"], self._shader, kwargs.get("sourcefilter"))

        elif "sourcecode" in kwargs:
            self._shader.SetSourceCode(kwargs["sourcecode"], "xac")

    def __del__(self):
        self.dispose()

    def dispose(self):
        self._stage.RemovePrim(self._shader.GetPrim().GetPath())

    def _add_shader_input(self, name: str, type: Sdf.ValueTypeName, index: int) -> UsdShade.Input:
        input = self._shader.CreateInput(name, type)
        input.GetAttr().SetCustomDataByKey("nvindex.param", Vt.Int(index))
        return input

    def _create_colormap_input(self, name: str = "colormap") -> UsdShade.Input:
        input = self._shader.CreateInput(name, Sdf.ValueTypeNames.Token)
        return input

    def get_usd_shader(self) -> UsdShade.Shader:
        return self._shader

    def release_inputs(self):
        attributes_to_remove: list[Usd.Attribute] = []
        for input in self._shader.GetInputs():
            if input.GetBaseName().startswith("fieldparam_"):
                attributes_to_remove.append(input.GetAttr())
            if input.GetBaseName().startswith("slot_"):
                attributes_to_remove.append(input.GetAttr())

        for attr in attributes_to_remove:
            prim = attr.GetPrim()
            prim.RemoveProperty(attr.GetName())


class RegularVolumeShader(VolumeShader):
    def __init__(self, stage, shaderpath: Sdf.Path):
        super().__init__(stage, shaderpath, sourceasset=str(SHADERS_PATH / "xac_basic_sparse_volume_rendering.cuh"))
        self._create_colormap_input()
        self._add_shader_input("sun_lon", Sdf.ValueTypeNames.Float, 0).Set(0)
        self._add_shader_input("sun_lat", Sdf.ValueTypeNames.Float, 1).Set(0)

    @property
    def sun_lat(self):
        return self._shader.GetInput("sun_lat").Get()

    @sun_lat.setter
    def sun_lat(self, lat: float):
        self._shader.GetInput("sun_lat").Set(lat)

    @property
    def sun_lon(self):
        return self._shader.GetInput("sun_lon").Get()

    @sun_lon.setter
    def sun_lon(self, lon: float):
        self._shader.GetInput("sun_lon").Set(lon)

    @property
    def colormap(self) -> Sdf.Path:
        self._shader.GetInput("colormap").GetConnectedSource()

    @colormap.setter
    def colormap(self, colormappath: Sdf.Path):
        self._shader.GetInput("colormap").ConnectToSource(colormappath)


class SphericalProjectionShader(VolumeShader):
    _sampler_types: list[ShaderSamplerType]
    _base_shader_parameter_index: int
    _code_gen: CodeGen

    def __init__(self, stage: Usd.Stage, shaderpath: Sdf.Path, sampler_type: str = "float"):
        self._sampler_types = []
        self._code_gen = CodeGen(
            str(SHADERS_PATH / "xac_irregular-volume_mapping-nvdb-scream.cuh.j2"),
            "xac_irregular-volume_mapping-nvdb-scream",
        )

        self._code_gen.update_codegen_dict(
            {
                "fields": [],
            }
        )
        super().__init__(stage, shaderpath, sourceasset=self._code_gen.generate_file_path)
        self._create_colormap_input()
        self._add_shader_input("sun_lon", Sdf.ValueTypeNames.Float, 0).Set(0)
        self._add_shader_input("sun_lat", Sdf.ValueTypeNames.Float, 1).Set(0)
        self._add_shader_input("slab_base_radius", Sdf.ValueTypeNames.Float, 2).Set(4950)
        self._add_shader_input("slab_thickness", Sdf.ValueTypeNames.Float, 3).Set(100)
        self._base_shader_parameter_index = 4

    def __del__(self):
        self.dispose()
        super().__del__()

    def dispose(self):
        self._code_gen.dispose()  # Try and make sure to cleanup the watch is enabled
        super().dispose()

    def rebuild_shader(self, volume_to_slot: dict[Sdf.Path, int], field_desc: list[FieldDescriptor]):
        self.release_inputs()

        for volume_path, volume_index in volume_to_slot.items():
            inp = self._shader.CreateInput(f"slot_{volume_index}", Sdf.ValueTypeNames.Token)
            inp.ConnectToSource(volume_path.AppendProperty("outputs:volume"))

        base_index = self._base_shader_parameter_index
        for field in field_desc:
            self._add_shader_input(f"fieldparam_{field.name}_lat_range", Sdf.ValueTypeNames.Float2, base_index).Set(
                (field.lat_range[0] / 90.0, field.lat_range[1] / 90)
            )
            self._add_shader_input(f"fieldparam_{field.name}_lon_range", Sdf.ValueTypeNames.Float2, base_index + 1).Set(
                (field.lon_range[0] / 180.0, field.lon_range[1] / 180.0)
            )
            self._add_shader_input(f"fieldparam_{field.name}_alt_range", Sdf.ValueTypeNames.Float2, base_index + 2).Set(
                (
                    (field.alt_range[0] - PROJECTION_SETTINGS.slab_base_radius) / PROJECTION_SETTINGS.slab_thickness,
                    (field.alt_range[1] - PROJECTION_SETTINGS.slab_base_radius) / PROJECTION_SETTINGS.slab_thickness,
                )
            )
            self._add_shader_input(
                f"fieldparam_{field.name}_channel_index", Sdf.ValueTypeNames.Int, base_index + 4
            ).Set(field.channel_index)
            base_index += 5

        self._code_gen.update_codegen_dict(
            {
                "volume_to_slot": volume_to_slot,
                "fields": field_desc,
            }
        )

    @property
    def sun_lat(self) -> float:
        return self._shader.GetInput("sun_lat").Get()

    @sun_lat.setter
    def sun_lat(self, lat: float):
        self._shader.GetInput("sun_lat").Set(lat)

    @property
    def sun_lon(self) -> float:
        return self._shader.GetInput("sun_lon").Get()

    @sun_lon.setter
    def sun_lon(self, lon: float):
        self._shader.GetInput("sun_lon").Set(lon)

    @property
    def colormap(self) -> Sdf.Path:
        return self._shader.GetInput("colormap").GetConnectedSource()

    @colormap.setter
    def colormap(self, colormappath: Sdf.Path):
        self._shader.GetInput("colormap").ConnectToSource(colormappath)

    @property
    def slab_base_radius(self) -> float:
        return self._shader.GetInput("slab_base_radius").Get()

    @slab_base_radius.setter
    def slab_base_radius(self, radius: float):
        self._shader.GetInput("slab_base_radius").Set(radius)

    @property
    def slab_thickness(self) -> float:
        return self._shader.GetInput("slab_thickness").Get()

    @slab_thickness.setter
    def slab_thickness(self, thickness: float):
        self._shader.GetInput("slab_thickness").Set(thickness)


class Material(ABC):
    _shader: VolumeShader
    _material: UsdShade.Material

    def __init__(self, stage: Usd.Stage, materialpath: Sdf.Path):
        self._stage = stage
        self._material = UsdShade.Material.Define(stage, materialpath)
        self._material.CreateVolumeOutput("nvindex")

    def __del__(self):
        self.dispose()

    def dispose(self):
        self._stage.RemovePrim(self._material.GetPrim().GetPath())
        self._shader.dispose()

    def _create_colormap(self, name: str, colormap: Colormap) -> Usd.Prim:
        colormap_prim = self._stage.DefinePrim(self._material.GetPrim().GetPath().AppendChild(name), "Colormap")
        colormap_prim.CreateAttribute("outputs:colormap", Sdf.ValueTypeNames.Token)
        colormap_prim.CreateAttribute("colormapSource", Sdf.ValueTypeNames.String).Set("rgbaPoints")
        colormap_prim.CreateAttribute("xPoints", Sdf.ValueTypeNames.FloatArray).Set(colormap.xPoints)
        colormap_prim.CreateAttribute("rgbaPoints", Sdf.ValueTypeNames.Float4Array).Set(colormap.rgbaPoints)
        colormap_prim.CreateAttribute("domain", Sdf.ValueTypeNames.Float2).Set(colormap.domain)

        return colormap_prim

    def _expose_shader_parameter(self, shader: VolumeShader, name: str):
        shader_input = shader.get_usd_shader().GetInput(name)
        exposed_input = self._material.CreateInput(name, shader_input.GetTypeName())
        shader_input.GetAttr().Clear()
        shader_input.ConnectToSource(exposed_input)

        return exposed_input

    def get_usd_material(self) -> UsdShade.Material:
        return self._material


class RegularVolumeMaterial(Material):
    _shader: RegularVolumeShader

    def __init__(self, stage: Usd.Stage, materialpath: Sdf.Path, colormap: Colormap, field: RegularVolume):
        super().__init__(stage, materialpath)
        self._shader = RegularVolumeShader(stage, materialpath.AppendChild("Shader"))
        self._material.GetVolumeOutput("nvindex").ConnectToSource(self._shader.get_usd_shader().GetOutput("volume"))

        colormap_prim = self._create_colormap("Colormap", colormap)
        self._shader.colormap = colormap_prim.GetAttribute("outputs:colormap").GetPath()
        UsdShade.MaterialBindingAPI.Apply(field._volume.GetPrim())
        UsdShade.MaterialBindingAPI(field._volume.GetPrim()).Bind(self.get_usd_material())

        if data_loader := field.data_loader:
            self._material.CreateOutput("nvindex:compute", Sdf.ValueTypeNames.Token).ConnectToSource(
                data_loader.get_usd_data_loader().GetOutput("compute")
            )


class SphericalProjectionMaterial(Material):
    _stage: Usd.Stage

    def __init__(
        self, stage: Usd.Stage, materialpath: Sdf.Path, colormap: Colormap, spherical_volume: SphericalProjectionVolume
    ):
        super().__init__(stage, materialpath)
        self._shader = SphericalProjectionShader(
            stage, materialpath.AppendChild("Shader"), "float"
        )  # FIXME: Sample type should be in each shader
        self._material.GetVolumeOutput("nvindex").ConnectToSource(self._shader.get_usd_shader().GetOutput("volume"))

        colormap_prim = self._create_colormap("Colormap", colormap)
        self._shader.colormap = colormap_prim.GetAttribute("outputs:colormap").GetPath()

        UsdShade.MaterialBindingAPI.Apply(spherical_volume._volume.GetPrim())
        UsdShade.MaterialBindingAPI(spherical_volume._volume.GetPrim()).Bind(self.get_usd_material())

    def rebuild_material(self, field_descriptors: list[FieldDescriptor]):
        all_volumes_paths = frozenset(field_desc.volume.volume.GetPrim().GetPath() for field_desc in field_descriptors)
        volume_to_slot = dict((y, x) for x, y in enumerate(all_volumes_paths))
        self._shader.rebuild_shader(volume_to_slot, field_descriptors)

    @property
    def sun_lat(self):
        return self._shader.sun_lat

    @sun_lat.setter
    def sun_lat(self, lat: float):
        self._shader.sun_lat = lat

    @property
    def sun_lon(self):
        return self._shader.sun_lon

    @sun_lon.setter
    def sun_lon(self, lon: float):
        self._shader.sun_lon = lon

    @property
    def slab_base_radius(self):
        return self._shader.slab_base_radius

    @slab_base_radius.setter
    def slab_base_radius(self, radius: float):
        self._shader.slab_base_radius = radius

    @property
    def slab_thickness(self):
        return self._shader.slab_thickness

    @slab_thickness.setter
    def slab_thickness(self, thickness: float):
        self._shader.slab_thickness = thickness

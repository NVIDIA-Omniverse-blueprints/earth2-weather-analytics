# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = ["ShaderConnectionSpec", "ShaderSpec", "ShaderLibrary"]

import omni.client
import carb

from typing import List
from pxr import Usd, UsdShade, Sdf, Tf

class ShaderConnectionSpec:
    def __init__(self, name:str, type_name:Sdf.ValueTypeName, render_type=None):
        self.name = name
        self.type_name = type_name
        self.render_type = render_type
        self.connection = None

    def _create_connection(self, shader_prim:UsdShade.Shader, output:bool):
        if output == False:
            self.connection = shader_prim.CreateInput(self.name, self.type_name)
        else:
            self.connection = shader_prim.CreateOutput(self.name, self.type_name)

        if self.connection and self.render_type:
            self.connection.SetRenderType(self.render_type)

        return self.connection
    def create_input(self, shader_prim:UsdShade.Shader):
        return self._create_connection(shader_prim, output=False)

    def create_output(self, shader_prim:UsdShade.Shader):
        return self._create_connection(shader_prim, output=True)

class ShaderSpec:
    def __init__(self, name:str, mdl_path:Sdf.AssetPath, sub_identifier:str,
            input_spec:List[ShaderConnectionSpec]=None, output_spec:List[ShaderConnectionSpec]=None):
        self.name = name
        self.mdl_path = mdl_path
        self.sub_identifier = sub_identifier
        self.input_spec = input_spec
        self.output_spec = output_spec

class ShaderLibrary:
    def __init__(self, ext_path):
        self._base_path = f'{ext_path}/data/shaders'
        self._colormap_path = f'{ext_path}/data/colormaps'

        # Populate Shader Library
        self._shaders = {}
        # ----------------------------------------
        # LayeredMaterial Shader
        # ----------------------------------------
        self._shaders['LayeredMaterial'] = ShaderSpec('LayeredMaterial',
                self.get_shader_path('LayeredMaterial'), 'LayeredMaterial',
                [ # Inputs
                    ShaderConnectionSpec('layer', Sdf.ValueTypeNames.Float4),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Token, 'material'),
                    ])
        # ----------------------------------------
        # BasicMaterial Shader
        # ----------------------------------------
        self._shaders['BasicMaterial'] = ShaderSpec('BasicMaterial',
                self.get_shader_path('BasicMaterial'), 'BasicMaterial',
                [ # Inputs
                    ShaderConnectionSpec('diffuse_color', Sdf.ValueTypeNames.Color3f),
                    ShaderConnectionSpec('diffuse_color_primvar', Sdf.ValueTypeNames.String),
                    ShaderConnectionSpec('emission_intensity', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('emission_color', Sdf.ValueTypeNames.Color3f),
                    ShaderConnectionSpec('emission_color_primvar', Sdf.ValueTypeNames.String),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Token, 'material'),
                    ])
        # ----------------------------------------
        # layering Shaders
        # ----------------------------------------
        self._shaders['merge'] = ShaderSpec('merge',
                self.get_shader_path('layering'), 'merge',
                [ # Inputs
                    ShaderConnectionSpec('A', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('B', Sdf.ValueTypeNames.Float4),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float4, 'float4'),
                    ])
        self._shaders['merge_2'] = ShaderSpec('merge_2',
                self.get_shader_path('layering'), 'merge_2',
                [ # Inputs
                    ShaderConnectionSpec('L0_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L0', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L1_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L1', Sdf.ValueTypeNames.Float4),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float4, 'float4'),
                    ])
        self._shaders['merge_10'] = ShaderSpec('merge_10',
                self.get_shader_path('layering'), 'merge_10',
                [ # Inputs
                    ShaderConnectionSpec('L0_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L0', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L1_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L1', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L2_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L2', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L3_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L3', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L4_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L4', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L5_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L5', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L6_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L6', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L7_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L7', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L8_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L8', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('L9_active', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('L9', Sdf.ValueTypeNames.Float4),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float4, 'float4'),
                    ])
        self._shaders['create_layer'] = ShaderSpec('create_layer',
                self.get_shader_path('layering'), 'create_layer(color,float)',
                [ # Inputs
                    ShaderConnectionSpec('value', Sdf.ValueTypeNames.Color3f),
                    ShaderConnectionSpec('alpha', Sdf.ValueTypeNames.Float),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float4, 'float4'),
                    ])
        self._shaders['lut_color_transfer'] = ShaderSpec('lut_color_transfer',
                self.get_shader_path('layering'), 'lut_color_transfer',
                [ # Inputs
                    ShaderConnectionSpec('layer', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('lut', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('channel', Sdf.ValueTypeNames.Int),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float4, 'float4'),
                    ])
        self._shaders['remap_layer'] = ShaderSpec('remap_layer',
                self.get_shader_path('layering'), 'remap_layer',
                [ # Inputs
                    ShaderConnectionSpec('layer', Sdf.ValueTypeNames.Float4),
                    ShaderConnectionSpec('input_min', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('input_max', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('output_min', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('output_max', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('output_gamma', Sdf.ValueTypeNames.Float),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float4, 'float4'),
                    ])
        # ----------------------------------------
        # mapping Shaders
        # ----------------------------------------
        def create_latlon_texture_base_inputs():
            return [
                    ShaderConnectionSpec('longitudinal_offset', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('flip_u', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('flip_v', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('use_affine', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('affine_row1', Sdf.ValueTypeNames.Float3),
                    ShaderConnectionSpec('affine_row2', Sdf.ValueTypeNames.Float3),
                    ShaderConnectionSpec('black_outside', Sdf.ValueTypeNames.Bool)]
        def create_split_texture_inputs(split_u, split_v):
            return [ShaderConnectionSpec(f'texture_{j}_{i}', Sdf.ValueTypeNames.Asset)
                    for j in range(split_v) for i in range(split_u)]

        # Latlon Textures
        self._shaders['lookup_latlong_texture'] = ShaderSpec('lookup_latlong_texture',
                self.get_shader_path('mapping'), 'lookup_latlong_texture',
                # Inputs
                [ ShaderConnectionSpec('texture', Sdf.ValueTypeNames.Asset) ]
                + create_latlon_texture_base_inputs(),
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Color3f, 'color'),
                    ])
        self._shaders['lookup_latlong_texture_mono'] = ShaderSpec('lookup_latlong_texture_mono',
                self.get_shader_path('mapping'), 'lookup_latlong_texture_mono',
                # Inputs
                [ ShaderConnectionSpec('texture', Sdf.ValueTypeNames.Asset) ]
                + create_latlon_texture_base_inputs(),
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float, 'float'),
                    ])

        # Latlon Splits
        for split_u, split_v in [(4,2), (2,1), (2,2)]:
            for mode in ['', '_mono']:
                self._shaders[f'lookup_latlong_texture_split_{split_u}_{split_v}{mode}'] = ShaderSpec(f'lookup_latlong_texture_split_{split_u}_{split_v}{mode}',
                        self.get_shader_path('mapping'), f'lookup_latlong_texture_split_{split_u}_{split_v}{mode}',
                        # Inputs
                        create_split_texture_inputs(split_u,split_v) +
                        create_latlon_texture_base_inputs(),
                        [ # Outputs
                            ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float, 'float') if mode == '_mono' else
                            ShaderConnectionSpec('out', Sdf.ValueTypeNames.Color3f, 'color')
                            ])
        # GOES Textures
        def create_goes_texture_common_inputs():
            return [
                    ShaderConnectionSpec('longitudinal_offset', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('perspective_point_height', Sdf.ValueTypeNames.Float),
                    ShaderConnectionSpec('x_range', Sdf.ValueTypeNames.Float2),
                    ShaderConnectionSpec('y_range', Sdf.ValueTypeNames.Float2),
                    ShaderConnectionSpec('flip_u', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('flip_v', Sdf.ValueTypeNames.Bool),
                    ShaderConnectionSpec('black_outside', Sdf.ValueTypeNames.Bool)]
        def create_goes_texture_base_inputs():
            return [
                    ShaderConnectionSpec('x_range', Sdf.ValueTypeNames.Float2),
                    ShaderConnectionSpec('y_range', Sdf.ValueTypeNames.Float2)]

        self._shaders['lookup_goes_texture'] = ShaderSpec('lookup_goes_texture',
                self.get_shader_path('mapping'), 'lookup_goes_texture',
                # Inputs
                [ ShaderConnectionSpec('texture', Sdf.ValueTypeNames.Asset) ]
                + create_goes_texture_common_inputs() + create_goes_texture_base_inputs(),
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Color3f, 'color'),
                    ])
        self._shaders['lookup_goes_texture_mono'] = ShaderSpec('lookup_goes_texture_mono',
                self.get_shader_path('mapping'), 'lookup_goes_texture_mono',
                # Inputs
                [ ShaderConnectionSpec('texture', Sdf.ValueTypeNames.Asset) ]
                + create_goes_texture_common_inputs() + create_goes_texture_base_inputs(),
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float, 'float'),
                    ])
        # GOES Disk
        self._shaders['lookup_goes_disk_texture'] = ShaderSpec('lookup_goes_disk_texture',
                self.get_shader_path('mapping'), 'lookup_goes_disk_texture',
                # Inputs
                [ ShaderConnectionSpec('texture', Sdf.ValueTypeNames.Asset) ]
                + create_goes_texture_common_inputs(),
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Color3f, 'color'),
                    ])
        self._shaders['lookup_goes_disk_texture_mono'] = ShaderSpec('lookup_goes_disk_texture_mono',
                self.get_shader_path('mapping'), 'lookup_goes_disk_texture_mono',
                # Inputs
                [ ShaderConnectionSpec('texture', Sdf.ValueTypeNames.Asset) ]
                + create_goes_texture_common_inputs(),
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float, 'float'),
                    ])

        # Diamond Textures
        self._shaders['lookup_diamond_texture'] = ShaderSpec('lookup_diamond_texture',
                self.get_shader_path('mapping'), 'lookup_diamond_texture',
                [ # Inputs
                    ShaderConnectionSpec('diamond_0', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_1', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_2', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_3', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_4', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_5', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_6', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_7', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_8', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_9', Sdf.ValueTypeNames.Asset),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Color3f, 'color'),
                    ])
        self._shaders['lookup_diamond_texture_mono'] = ShaderSpec('lookup_diamond_texture_mono',
                self.get_shader_path('mapping'), 'lookup_diamond_texture_mono',
                [ # Inputs
                    ShaderConnectionSpec('diamond_0', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_1', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_2', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_3', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_4', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_5', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_6', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_7', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_8', Sdf.ValueTypeNames.Asset),
                    ShaderConnectionSpec('diamond_9', Sdf.ValueTypeNames.Asset),
                    ],
                [ # Outputs
                    ShaderConnectionSpec('out', Sdf.ValueTypeNames.Float, 'float'),
                    ])

    def get_shader_path(self, name:str):
        return f'{self._base_path}/{name}.mdl'

    def get_colormap_path(self, name:str):
        return f'{self._colormap_path}/{name}.png'

    def get_colormaps(self):
        (result, entries) = omni.client.list(self._colormap_path)
        if result != omni.client.Result.OK:
            carb.log_error('Could not stat colormap directory: {self._colormap_path}, error: {result}')
        result = [e.relative_path[:-4] for e in entries if e.relative_path[-4:]=='.png']
        return result

    def get_shader_spec(self, name:str):
        if name in self._shaders:
            return self._shaders[name]
        else:
            return None

    def get_shaders(self):
        return self._shaders

    def add_shader(self, name:str, shader_spec:ShaderSpec):
        if name not in self._shaders:
            self._shaders[name] = shader_spec

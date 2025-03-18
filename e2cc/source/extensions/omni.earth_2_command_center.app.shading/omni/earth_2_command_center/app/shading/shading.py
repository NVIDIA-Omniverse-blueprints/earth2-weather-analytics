# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import os
import pathlib
from typing import List
import asyncio
from functools import partial
import uuid

import carb

import omni.kit.app
import omni.ext
import omni.usd
import omni.kit.commands
import omni.kit.async_engine as async_engine

from pxr import Usd, UsdShade, UsdGeom, Sdf, Gf, Vt

from .shader_library import *

import omni.earth_2_command_center.app.core as e2_core
import omni.earth_2_command_center.app.core.features_api as e2_features_api

EXTENSION_FOLDER_PATH = pathlib.Path(
    omni.kit.app.get_app().get_extension_manager().get_extension_path_by_module(__name__)
)

#class ShadingExtension(omni.ext.IExt):
#    def on_startup(self, ext_id):
#        self._ext_id = ext_id

_shader_library = None
def get_shader_library():
    global _shader_library
    if not _shader_library:
        _shader_library = ShaderLibrary(EXTENSION_FOLDER_PATH)
    return _shader_library

def simple_update_func(stage, attr_path, payload):
    if not attr_path.IsPrimPropertyPath():
        carb.log_error('Not a Prim Property Path: \'attr_path\'')
        return False
    prim_path = attr_path.GetPrimPath()
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        carb.log_error(f'Prim not found for update: {prim_path}')
        return False
    property_name = attr_path.name
    attr = prim.GetAttribute(property_name)
    if not attr:
        carb.log_error(f'Attribute not update for update: {attr_path}')
        return False
    attr.Set(payload['new_value'])
    return True

def remapping_update_func(stage, shader_path, payload):
    if not shader_path.IsPrimPropertyPath():
        carb.log_error('Not a Prim Property Path: \'shader_path\'')
        return False
    shader_prim = UsdShade.Shader(stage.GetPrimAtPath(shader_path.GetPrimPath()))
    if not shader_prim:
        carb.log_error(f'Shader Prim not found for update: {shader_path}')
        return False

    for param in ['input_min', 'input_max', 'output_min', 'output_max', 'output_gamma']:
        input = shader_prim.GetInput(param)
        if input:
            input.Set(payload['new_value'][param])
    return True

def colormap_update_func(stage, shader_path, payload):
    if not shader_path.IsPrimPropertyPath():
        carb.log_error('Not a Prim Property Path: \'shader_path\'')
        return False
    shader_prim = UsdShade.Shader(stage.GetPrimAtPath(shader_path.GetPrimPath()))
    if not shader_prim:
        carb.log_error(f'Shader Prim not found for update: {shader_path}')
        return False

    new_colormap = payload['new_value']
    if new_colormap is None:
        # trigger recompilation
        return False

    colormap_path = get_shader_library().get_colormap_path(new_colormap)
    shader_prim.GetInput('lut').Set(colormap_path)
    return True

def create_shader_prim(stage:Usd.Stage,
        path:Sdf.Path, shader_spec:ShaderSpec):
    shader_prim = UsdShade.Shader.Define(stage, path)

    shader_prim.GetImplementationSourceAttr().Set(UsdShade.Tokens.sourceAsset)
    shader_prim.SetSourceAsset(shader_spec.mdl_path, 'mdl')
    shader_prim.SetSourceAssetSubIdentifier(shader_spec.sub_identifier, 'mdl')
    #await omni.kit.app.get_app().next_update_async()

    # TODO: need to get the usd context as param
    #await omni.usd.get_context().load_mdl_parameters_for_prim_async(shader_prim.GetPrim())
    #await omni.kit.app.get_app().next_update_async()

    # NOTE: The Usd material watcher creates inputs and outputs but when testing
    # things in isolation, we can't rely on it

    # create inputs
    for spec in shader_spec.input_spec:
        cur_input = spec.create_input(shader_prim)

    # create outputs
    for spec in shader_spec.output_spec:
        cur_output = spec.create_output(shader_prim)
    #await omni.kit.app.get_app().next_update_async()

    return shader_prim

def create_material_prim(stage:Usd.Stage, path:Sdf.Path, shader_spec:ShaderSpec):
    # create the prims
    material_prim = UsdShade.Material.Define(stage, path)
    #omni.usd.get_context().add_to_pending_creating_mdl_paths(str(material_prim.GetPath()), False, False)
    #await omni.kit.app.get_app().next_update_async()

    material_prim = UsdShade.Material(stage.GetPrimAtPath(path))

    shader_prim = create_shader_prim(stage, path=path.AppendChild('Shader'),
            shader_spec=shader_spec)
    shader_out = shader_prim.GetOutput('out')

    material_prim.CreateSurfaceOutput('mdl').ConnectToSource(shader_out)
    material_prim.CreateVolumeOutput('mdl').ConnectToSource(shader_out)
    material_prim.CreateDisplacementOutput('mdl').ConnectToSource(shader_out)

    return material_prim, shader_prim

def create_layered_network(stage:Usd.Stage,
        features:List[e2_features_api.Feature] = None,
        base_path:Sdf.Path = None, update_mapping = {}):
    def add_to_update_mapping(feature, property_name, shader_input, update_callback):
        if property_name not in update_mapping[feature.id]:
            update_mapping[feature.id][property_name] = []
        update_mapping[feature.id][property_name].append(
                partial(update_callback, stage, shader_input.GetAttr().GetPath()))

    # helper function
    def create_layer(stage:Usd.Stage,
            base_path:Sdf.Path,
            feature:e2_features_api.Feature, name:str):
        shader_library = get_shader_library()

        # ----------------------------------------
        # create texture lookup
        # ----------------------------------------
        tex_lookup_prim = None
        if feature.sources:
            projection = feature.projection
            tex_lookup_spec = None
            if projection == 'latlong':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture')
            elif projection == 'latlong_4_2':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_split_4_2')
            elif projection == 'latlong_2_1':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_split_2_1')
            elif projection == 'latlong_2_2':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_split_2_2')
            elif projection == 'goes':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_goes_texture')
            elif projection == 'goes_disk':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_goes_disk_texture')
            elif projection == 'diamond':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_diamond_texture')
            else:
                raise ValueError('Unhandled Projection')

            tex_lookup_prim = create_shader_prim(stage,
                    base_path.AppendChild(f'{name}_tex_lookup'),
                    tex_lookup_spec)

            # connections & parameters
            if projection.startswith('latlong') or projection in ['goes', 'goes_disk']:
                # common latlong setup
                if feature.longitudinal_offset:
                    tex_lookup_prim.GetInput('longitudinal_offset').Set(feature.longitudinal_offset)
                add_to_update_mapping(feature, 'longitudinal_offset', tex_lookup_prim.GetInput('longitudinal_offset'), simple_update_func)

                tex_lookup_prim.GetInput('flip_u').Set(feature.flip_u)
                add_to_update_mapping(feature, 'flip_u', tex_lookup_prim.GetInput('flip_u'), simple_update_func)
                tex_lookup_prim.GetInput('flip_v').Set(feature.flip_v)
                add_to_update_mapping(feature, 'flip_v', tex_lookup_prim.GetInput('flip_v'), simple_update_func)

            # latlon specific
            if projection.startswith('latlong'):
                if feature.affine is not None:
                    # TODO: need additional update function
                    tex_lookup_prim.GetInput('use_affine').Set(True)
                    tex_lookup_prim.GetInput('affine_row1').Set(Gf.Vec3f(feature.affine[0:3]))
                    tex_lookup_prim.GetInput('affine_row2').Set(Gf.Vec3f(feature.affine[3:]))

            # goes specific
            if projection == 'goes' and feature.meta is not None:
                # TODO: add update functions for animated params
                if 'x_range' in feature.meta:
                    tex_lookup_prim.GetInput('x_range').Set(Gf.Vec2f(*feature.meta['x_range']))
                if 'y_range' in feature.meta:
                    tex_lookup_prim.GetInput('y_range').Set(Gf.Vec2f(*feature.meta['y_range']))
            if projection in ['goes', 'goes_disk'] and feature.meta is not None:
                if 'perspective_point_height' in feature.meta:
                    tex_lookup_prim.GetInput('perspective_point_height').Set(feature.meta['perspective_point_height'])

            if projection == 'latlong' or projection in ['goes', 'goes_disk']:
                tex_lookup_prim.GetInput('texture').Set(feature.sources[0])
                # TODO: need additional update function
            # TODO: we can do that in a loop
            if projection == 'latlong_4_2':
                tex_lookup_prim.GetInput('texture_0_0').Set(feature.sources[0])
                tex_lookup_prim.GetInput('texture_0_1').Set(feature.sources[1])
                tex_lookup_prim.GetInput('texture_0_2').Set(feature.sources[2])
                tex_lookup_prim.GetInput('texture_0_3').Set(feature.sources[3])
                tex_lookup_prim.GetInput('texture_1_0').Set(feature.sources[4])
                tex_lookup_prim.GetInput('texture_1_1').Set(feature.sources[5])
                tex_lookup_prim.GetInput('texture_1_2').Set(feature.sources[6])
                tex_lookup_prim.GetInput('texture_1_3').Set(feature.sources[7])
                # TODO: need additional update function
            if projection == 'latlong_2_1':
                tex_lookup_prim.GetInput('texture_0_0').Set(feature.sources[0])
                tex_lookup_prim.GetInput('texture_0_1').Set(feature.sources[1])
                # TODO: need additional update function
            if projection == 'latlong_2_2':
                tex_lookup_prim.GetInput('texture_0_0').Set(feature.sources[0])
                tex_lookup_prim.GetInput('texture_0_1').Set(feature.sources[1])
                tex_lookup_prim.GetInput('texture_1_0').Set(feature.sources[2])
                tex_lookup_prim.GetInput('texture_1_1').Set(feature.sources[3])
                # TODO: need additional update function

            if projection == 'diamond':
                if len(feature.sources) < 10:
                    raise ValueError("Image Feature with diamond projection but < 10 sources")
                for i in range(10):
                    tex_lookup_prim.GetInput(f'diamond_{i}').Set(feature.sources[i])

        alpha_tex_lookup_prim = None
        if feature.alpha_sources:
            projection = feature.projection
            tex_lookup_spec = None

            if projection == 'latlong':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_mono')
            elif projection == 'latlong_4_2':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_split_4_2_mono')
            elif projection == 'latlong_2_1':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_split_2_1_mono')
            elif projection == 'latlong_2_2':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_latlong_texture_split_2_2_mono')
            elif projection == 'goes':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_goes_texture_mono')
            elif projection == 'goes_disk':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_goes_disk_texture_mono')
            elif projection == 'diamond':
                tex_lookup_spec = shader_library.get_shader_spec('lookup_diamond_texture_mono')
            else:
                raise ValueError('Unhandled Projection')

            alpha_tex_lookup_prim = create_shader_prim(stage,
                    base_path.AppendChild(f'{name}_alpha_tex_lookup'),
                    tex_lookup_spec)

            # connections & parameters
            if projection.startswith('latlong') or projection in ['goes', 'goes_disk']:
                # common latlong setup
                if feature.longitudinal_offset:
                    alpha_tex_lookup_prim.GetInput('longitudinal_offset').Set(feature.longitudinal_offset)
                add_to_update_mapping(feature, 'longitudinal_offset', alpha_tex_lookup_prim.GetInput('longitudinal_offset'), simple_update_func)

                alpha_tex_lookup_prim.GetInput('flip_u').Set(feature.flip_u)
                add_to_update_mapping(feature, 'flip_u', alpha_tex_lookup_prim.GetInput('flip_u'), simple_update_func)
                alpha_tex_lookup_prim.GetInput('flip_v').Set(feature.flip_v)
                add_to_update_mapping(feature, 'flip_v', alpha_tex_lookup_prim.GetInput('flip_v'), simple_update_func)

            if projection.startswith('latlong'):
                if feature.affine is not None:
                    alpha_tex_lookup_prim.GetInput('use_affine').Set(True)
                    alpha_tex_lookup_prim.GetInput('affine_row1').Set(Gf.Vec3f(feature.affine[0:3]))
                    alpha_tex_lookup_prim.GetInput('affine_row2').Set(Gf.Vec3f(feature.affine[3:]))
                    # TODO: need additional update function

            # goes specific
            if projection == 'goes' and feature.meta is not None:
                # TODO: add update functions for animated params
                if 'x_range' in feature.meta:
                    alpha_tex_lookup_prim.GetInput('x_range').Set(Gf.Vec2f(*feature.meta['x_range']))
                if 'y_range' in feature.meta:
                    alpha_tex_lookup_prim.GetInput('y_range').Set(Gf.Vec2f(*feature.meta['y_range']))
            if projection in ['goes', 'goes_disk'] and feature.meta is not None:
                if 'perspective_point_height' in feature.meta:
                    alpha_tex_lookup_prim.GetInput('perspective_point_height').Set(feature.meta['perspective_point_height'])

            if projection == 'latlong' or projection in ['goes', 'goes_disk']:
                alpha_tex_lookup_prim.GetInput('texture').Set(feature.alpha_sources[0])
                # TODO: need additional update function

            # TODO: we can do that in a loop
            if projection == 'latlong_4_2':
                alpha_tex_lookup_prim.GetInput('texture_0_0').Set(feature.alpha_sources[0])
                alpha_tex_lookup_prim.GetInput('texture_0_1').Set(feature.alpha_sources[1])
                alpha_tex_lookup_prim.GetInput('texture_0_2').Set(feature.alpha_sources[2])
                alpha_tex_lookup_prim.GetInput('texture_0_3').Set(feature.alpha_sources[3])
                alpha_tex_lookup_prim.GetInput('texture_1_0').Set(feature.alpha_sources[4])
                alpha_tex_lookup_prim.GetInput('texture_1_1').Set(feature.alpha_sources[5])
                alpha_tex_lookup_prim.GetInput('texture_1_2').Set(feature.alpha_sources[6])
                alpha_tex_lookup_prim.GetInput('texture_1_3').Set(feature.alpha_sources[7])
                # TODO: need additional update function
            if projection == 'latlong_2_1':
                alpha_tex_lookup_prim.GetInput('texture_0_0').Set(feature.alpha_sources[0])
                alpha_tex_lookup_prim.GetInput('texture_0_1').Set(feature.alpha_sources[1])
                # TODO: need additional update function
            if projection == 'latlong_2_2':
                alpha_tex_lookup_prim.GetInput('texture_0_0').Set(feature.alpha_sources[0])
                alpha_tex_lookup_prim.GetInput('texture_0_1').Set(feature.alpha_sources[1])
                alpha_tex_lookup_prim.GetInput('texture_1_0').Set(feature.alpha_sources[2])
                alpha_tex_lookup_prim.GetInput('texture_1_1').Set(feature.alpha_sources[3])
                # TODO: need additional update function

            if projection == 'diamond':
                if len(feature.alpha_sources) < 10:
                    raise ValueError("Image Feature with diamond projection but < 10 alpha sources")
                for i in range(10):
                    alpha_tex_lookup_prim.GetInput(f'diamond_{i}').Set(feature.alpha_sources[i])
                # TODO: need additional update function

        # ----------------------------------------
        # create layer node
        # ----------------------------------------
        create_layer_spec = shader_library.get_shader_spec('create_layer')
        create_layer_prim = create_shader_prim(stage,
                base_path.AppendChild(f'{name}_create_layer'),
                create_layer_spec)
        # connections & parameters
        if feature.sources:
            create_layer_prim.GetInput('value').ConnectToSource(tex_lookup_prim.GetOutput('out'))
        else:
            create_layer_prim.GetInput('value').Set((1,1,1))
        # TODO: need additional update function
        if feature.alpha_sources:
            create_layer_prim.GetInput('alpha').ConnectToSource(alpha_tex_lookup_prim.GetOutput('out'))
        else:
            create_layer_prim.GetInput('alpha').Set(1.0)
        # TODO: need additional update function
        prev_node = create_layer_prim

        # ----------------------------------------
        # remap layer node
        # ----------------------------------------
        if feature.remapping is not None and len(feature.remapping) > 0:
            remap_layer_spec = shader_library.get_shader_spec('remap_layer')
            remap_layer_prim = create_shader_prim(stage,
                    base_path.AppendChild(f'{name}_remap_layer'),
                    remap_layer_spec)
            remapping = feature.remapping
            # connections & parameters
            remap_layer_prim.GetInput('layer').ConnectToSource(prev_node.GetOutput('out'))
            for param in ['input_min', 'input_max', 'output_min', 'output_max', 'output_gamma']:
                if param in remapping:
                    input = remap_layer_prim.GetInput(param)
                    if input:
                        input.Set(remapping[param])
            add_to_update_mapping(feature, 'remapping', remap_layer_prim.GetInput('input_min'), remapping_update_func)
            prev_node = remap_layer_prim

        # ----------------------------------------
        # color transfer node
        # ----------------------------------------
        if feature.colormap is not None:
            color_transfer_spec = shader_library.get_shader_spec('lut_color_transfer')
            color_transfer_prim = create_shader_prim(stage,
                    base_path.AppendChild(f'{name}_color_transfer'),
                    color_transfer_spec)
            # connections & parameters
            if feature.colormap_source_channel is not None:
                color_transfer_prim.GetInput('channel').Set(feature.colormap_source_channel)
            else:
                if not feature.sources and feature.alpha_sources:
                    # Set to use alpha channel for transfer
                    color_transfer_prim.GetInput('channel').Set(3);
                else:
                    # Set to use red channel for transfer
                    color_transfer_prim.GetInput('channel').Set(0);
            colormap_path = shader_library.get_colormap_path(feature.colormap)
            color_transfer_prim.GetInput('lut').Set(colormap_path)
            # need to change the gamma
            attrs = color_transfer_prim.GetInput('lut').GetValueProducingAttributes()
            if attrs and len(attrs)>0:
                attrs[0].SetMetadata('colorSpace', Vt.Token('sRGB'))
            color_transfer_prim.GetInput('layer').ConnectToSource(prev_node.GetOutput('out'))
            prev_node = color_transfer_prim
            add_to_update_mapping(feature, 'colormap', color_transfer_prim.GetInput('lut'), colormap_update_func)

        return prev_node

    # list of layers
    layers = []

    # for each image feature, create a shading network to compose the result
    for idx,f in enumerate(features):
        #prev_layer = layers[-1] if len(layers) > 0 else None
        cur_layer = create_layer(stage, base_path, f, f'Layer_{idx+1:02d}')
        #if prev_layer:
        #    cur_layer.GetInput('A').ConnectToSource(prev_layer.GetOutput('out'))
        layers.append(cur_layer)

    return layers, update_mapping

def create_layered_shell_material(stage:Usd.Stage,
        base_path = Sdf.Path('/World/Looks/LayeredShell'),
        bind_path = None,
        features:List[e2_features_api.Feature] = None
        ):
    def add_to_update_mapping(feature, property_name, shader_input, update_callback):
        if property_name not in update_mapping[feature.id]:
            update_mapping[feature.id][property_name] = []
        update_mapping[feature.id][property_name].append(
                partial(update_callback, stage, shader_input.GetAttr().GetPath()))

    # if not explicitly specifying the features, we retrieve them from the
    # global state
    if features is None:
        e2_state = e2_core.get_state()
        features_api = e2_state.get_features_api()
        features = features_api.get_image_features()

    # create unique material path
    base_path = base_path.AppendChild(f'mat_{uuid.uuid4().hex}')

    # initialize update mapping
    update_mapping = {}
    for f in features:
        update_mapping[f.id] = {}

    layers, update_mapping = create_layered_network(stage, features, base_path, update_mapping)
    num_layers = len(features)

    # create main material
    layered_material_spec = get_shader_library().get_shader_spec('LayeredMaterial')
    material_prim, layered_material_prim = create_material_prim(stage,
            base_path,
            layered_material_spec)

    # connections & parameters
    # ----------------------------------------
    # create layer merge
    # ----------------------------------------
    # we merge layers in blocks of num_merge_slots as we don't have array support in MDL
    num_merge_slots = 10
    merge_layer_spec = get_shader_library().get_shader_spec(f'merge_{num_merge_slots}')
    if num_layers == 1 and features[0].active:
        # no merging required
        # but we want the merge shader to make it more reusable
        merge_layer_prim = create_shader_prim(stage,
                base_path.AppendChild(f'merge_{0:04d}'),
                merge_layer_spec)
        for i in range(num_merge_slots):
          merge_layer_prim.GetInput(f'L{i}_active').Set(False)
        merge_layer_prim.GetInput('L0').ConnectToSource(layers[-1].GetOutput('out'))
        merge_layer_prim.GetInput('L0_active').Set(True)
        layered_material_prim.GetInput('layer').ConnectToSource(merge_layer_prim.GetOutput('out'))

        # add to update mapping
        add_to_update_mapping(features[0], 'active', merge_layer_prim.GetInput('L0_active'), simple_update_func)

    elif num_layers > 1:
        cur_layer_idx = 0
        cur_merge_idx = 0
        layers_left = len(layers)
        prev_merge = None
        while layers_left > 0:
            merge_layer_prim = create_shader_prim(stage,
                    base_path.AppendChild(f'merge_{cur_merge_idx:04d}'),
                    merge_layer_spec)
            for i in range(num_merge_slots):
                    merge_layer_prim.GetInput(f'L{i}_active').Set(False)

            for i in range(num_merge_slots):
                if i==0 and prev_merge:
                    # if this isn't the first merge stage, we need to connect
                    # the previous one to the first layer of this one to
                    # daisy-chain them together
                    merge_layer_prim.GetInput('L0').ConnectToSource(prev_merge.GetOutput('out'))
                    merge_layer_prim.GetInput(f'L0_active').Set(True)
                    continue
                if layers_left > 0:
                    # connecting the layer to the input i of the current merge node
                    merge_layer_prim.GetInput(f'L{i}').ConnectToSource(layers[cur_layer_idx].GetOutput('out'))

                    merge_layer_prim.GetInput(f'L{i}_active').Set(features[cur_layer_idx].active)
                    # add to update mapping
                    add_to_update_mapping(features[cur_layer_idx], 'active', merge_layer_prim.GetInput(f'L{i}_active'), simple_update_func)

                    cur_layer_idx += 1
                    layers_left -= 1
                else:
                    # we're done so early out
                    break
            cur_merge_idx += 1
            prev_merge = merge_layer_prim

        # connect to main material
        layered_material_prim.GetInput('layer').ConnectToSource(prev_merge.GetOutput('out'))

    material_prim = UsdShade.Material(stage.GetPrimAtPath(base_path))
    if bind_path:
        bind_prim = stage.GetPrimAtPath(bind_path)
        if bind_prim and not bind_prim.HasAPI(UsdShade.MaterialBindingAPI):
            bind_prim.ApplyAPI(UsdShade.MaterialBindingAPI)
        if bind_prim:
            # Compilation of Shader can take a long time and there is no great
            # way to know when its done. Also, during compilation, a default white
            # material is used which causes flashing and is confusing to the user.
            #
            # The implemented solution to this is to:
            #  - create a dummy (emtpy) mesh and bind the new material to it
            #    to trigger the compilation of the material
            #  - subscribe to ASSETS_LOADED events and assume the next one comes
            #    from the shader compilation. if that assumption is false, there
            #    might still be white flashing but should occur only when
            #    compiling/loading multiple assets at the same time
            #  - once compilation is done, we remove the dummy mesh, bind the
            #    material to the actual prim and remove the previously bound
            #    materials

            def handling_recompilation(compilation_done_callback):
                # first check if there already is one of our notifications present
                from omni.kit.notification_manager import post_notification, get_all_notifications
                create_notification = True
                prompt = 'Recompiling Shader...'
                for n in get_all_notifications():
                    if n.info.text == prompt:
                        create_notification = False
                        break

                # post notification if required
                notification = None
                if create_notification:
                    notification = post_notification(prompt, hide_after_timeout=False)

                tmp_path = f'/World/tmp/shader_dummy_{uuid.uuid4().hex}'
                tmp_mesh = UsdGeom.Mesh.Define(stage, tmp_path)

                def callback(event):
                    if event.type == int(omni.usd.StageEventType.ASSETS_LOADED):
                        # dismiss notification if we created one
                        if notification is not None:
                            notification.dismiss()
                        sub.unsubscribe()
                        stage.RemovePrim(tmp_mesh.GetPath())
                        compilation_done_callback()

                stage_event_stream = omni.usd.get_context().get_stage_event_stream()
                sub = stage_event_stream.create_subscription_to_pop(callback)
                bindings_api = UsdShade.MaterialBindingAPI(bind_prim)
                bindings_api = UsdShade.MaterialBindingAPI(tmp_mesh).Bind(material_prim)

            # NOTE: this relies on callback being called in order, ie that the
            # last one called applies the most recent material
            def on_compilation_done():
                bindings_api = UsdShade.MaterialBindingAPI(bind_prim)
                cur_binding_rel = bindings_api.GetDirectBindingRel()
                cur_targets = cur_binding_rel.GetTargets()
                cur_binding_rel.ClearTargets(True)
                bindings_api.Bind(material_prim)
                for p in cur_targets:
                    if stage.GetPrimAtPath(p):
                        stage.RemovePrim(p)

            handling_recompilation(on_compilation_done)

    return material_prim, update_mapping

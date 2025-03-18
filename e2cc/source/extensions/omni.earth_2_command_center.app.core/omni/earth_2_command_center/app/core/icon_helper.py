# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


__all__ = [ 'ICONHelper' ]

import asyncio

import carb
import omni.usd
import omni.kit.async_engine as async_engine

import hpcvis.dynamictexture

from omni.kit.viewport.utility import get_active_viewport
from omni.kit.menu.utils import add_menu_items, remove_menu_items, MenuItemDescription

from pxr import Usd, UsdGeom, Tf, Gf, Sdf, Vt
import numpy as np

def combined_diamond_idx(diamond_idx, sub_idx):
    return diamond_idx+sub_idx*10

def diamond_idx_from_combined(combined_diamond_idx):
    sub_idx = combined_diamond_idx//10
    diamond_idx = combined_diamond_idx%10
    return (diamond_idx, sub_idx)

class Polygon:
    def __init__(self, vertices = []):
        self.vertices = vertices

    def size(self):
        return len(self.vertices)

    def get_area(self):
        # assume we can triangulate as triangle fan (convex polygon)
        if self.size() < 3:
            return 0

        mid_idx = 1
        area_sum = 0
        while mid_idx+1 < self.size():
            cur_triangle = (self.vertices[0], self.vertices[mid_idx], self.vertices[mid_idx+1])
            cur_area = self.get_triangle_area(cur_triangle[0], cur_triangle[1], cur_triangle[2])
            area_sum += max(0, cur_area)
            mid_idx += 1

        return area_sum

    @staticmethod
    def get_triangle_area_sqr(A, B, C):
        '''Heron's Formula'''
        a2 = (C[0]-B[0])**2 + (C[1]-B[1])**2
        b2 = (C[0]-A[0])**2 + (C[1]-A[1])**2
        c2 = (B[0]-A[0])**2 + (B[1]-A[1])**2
        return max(0, (0.5**4)*((a2+b2+c2)**2 - 2*(a2*a2 + b2*b2 + c2*c2)))

    @staticmethod
    def get_triangle_area(A, B, C):
        return np.sqrt(Polygon.get_triangle_area_sqr(A, B, C))

    def clip_to_range(self, xmin, xmax, ymin, ymax):
        def get_x_crossing(a, b, x_crossing):
            # we've crossed
            dist = (x_crossing-a[0])/(b[0]-a[0])
            y = dist*(b[1]-a[1]) + a[1]
            return (x_crossing, y)
        def get_y_crossing(a, b, y_crossing):
            # we've crossed
            dist = (y_crossing-a[1])/(b[1]-a[1])
            x = dist*(b[0]-a[0]) + a[0]
            return (x, y_crossing)

        # ========================================
        # xmin clipping 
        # ========================================
        cur_vertices = self.vertices
        next_vertices = []
        for i in range(len(cur_vertices)):
            next_idx = (i+1)%len(cur_vertices)

            cur_in = cur_vertices[i][0] >= xmin
            next_in = cur_vertices[next_idx][0] >= xmin

            # condition when we add the current vertex
            if (cur_in and next_in) or (cur_in and not next_in):
                next_vertices.append(cur_vertices[i])
            # condition when we add the crossing point
            if (cur_in != next_in):
                next_vertices.append(get_x_crossing(cur_vertices[i], cur_vertices[next_idx], xmin))

        # ========================================
        # xmax clipping 
        # ========================================
        cur_vertices = next_vertices
        next_vertices = []
        for i in range(len(cur_vertices)):
            next_idx = (i+1)%len(cur_vertices)

            cur_in = cur_vertices[i][0] <= xmax
            next_in = cur_vertices[next_idx][0] <= xmax

            # condition when we add the current vertex
            if (cur_in and next_in) or (cur_in and not next_in):
                next_vertices.append(cur_vertices[i])
            # condition when we add the crossing point
            if (cur_in != next_in):
                next_vertices.append(get_x_crossing(cur_vertices[i], cur_vertices[next_idx], xmax))

        # ========================================
        # ymin clipping 
        # ========================================
        cur_vertices = next_vertices
        next_vertices = []
        for i in range(len(cur_vertices)):
            next_idx = (i+1)%len(cur_vertices)

            cur_in = cur_vertices[i][1] >= ymin
            next_in = cur_vertices[next_idx][1] >= ymin

            # condition when we add the current vertex
            if (cur_in and next_in) or (cur_in and not next_in):
                next_vertices.append(cur_vertices[i])
            # condition when we add the crossing point
            if (cur_in != next_in):
                next_vertices.append(get_y_crossing(cur_vertices[i], cur_vertices[next_idx], ymin))

        # ========================================
        # ymax clipping 
        # ========================================
        cur_vertices = next_vertices
        next_vertices = []
        for i in range(len(cur_vertices)):
            next_idx = (i+1)%len(cur_vertices)

            cur_in = cur_vertices[i][1] <= ymax
            next_in = cur_vertices[next_idx][1] <= ymax

            # condition when we add the current vertex
            if (cur_in and next_in) or (cur_in and not next_in):
                next_vertices.append(cur_vertices[i])
            # condition when we add the crossing point
            if (cur_in != next_in):
                next_vertices.append(get_y_crossing(cur_vertices[i], cur_vertices[next_idx], ymax))

        # TODO: for now we change ourselves
        self.vertices = next_vertices

    def write_to_csv(self, path):
        with open(path, "w") as file:
            for x,y in self.vertices:
                file.write(f'{x}\t{y}\n')
            file.write(f'{self.vertices[0][0]}\t{self.vertices[0][1]}\n')

class ICONVertex:
    def __init__(self, pos, diamonds):
        self.pos = pos
        self.diamonds = set(diamonds)

class ICONFace:
    def __init__(self, indices, diamond, vertices=None):
        self.indices = indices
        self.diamond = diamond
        if vertices is not None:
            self.face_normal = self.compute_face_normal(vertices)
        else:
            self.face_normal = None

    def compute_face_normal(self, vertices):
        sum = Gf.Vec3d(0)
        for i in self.indices:
            sum += vertices[i].pos
        return sum.GetNormalized()

def icon_vertices_to_usdpoints(stage, path, vertices, width = 0.05):
    points = UsdGeom.Points.Define(stage, path)

    pos = [v.pos for v in vertices]

    points.CreatePointsAttr().Set(pos)
    points.CreateWidthsAttr().Set([width])
    points.SetWidthsInterpolation(UsdGeom.Tokens.constant)

    #UsdGeom.XformCommonAPI(points.GetPrim()).SetScale(Gf.Vec3f(scale))

    return points

def icon_faces_to_usdmesh(stage, path, faces, vertices, scale):
    mesh = UsdGeom.Mesh.Define(stage, path)

    verts = np.empty((len(vertices), 3))
    for i,v in enumerate(vertices):
        verts[i,:] = v.pos
    mesh.CreatePointsAttr().Set(verts)

    vertex_counts = []
    indices = []
    for f in faces:
        vertex_counts.append(len(f.indices))
        indices.extend(f.indices)

    mesh.CreateFaceVertexCountsAttr().Set(vertex_counts)
    mesh.CreateFaceVertexIndicesAttr().Set(indices)

    return mesh

def highlight_usdpoints_point(points_prim, idxs, color):
    display_color_primvar = points_prim.GetDisplayColorPrimvar()
    if display_color_primvar.GetInterpolation() != UsdGeom.Tokens.vertex:
        display_color_primvar.SetInterpolation(UsdGeom.Tokens.vertex)
    display_color = display_color_primvar.Get()
    num_points = points_prim.GetPointCount()

    if idxs is None:
        idxs = list(range(num_points))

    display_color_primvar.Set([
        color if i in idxs else display_color[i] for i in range(num_points)])

def get_closest_to_camera(icon_vertices, cam_pos):
    dot_products = [Gf.Dot(v.pos, cam_pos) for v in icon_vertices]
    return dot_products

def construct_icon_vertices():
    icon_vertices = []
    icon_faces = []
    
    # north pole
    icon_vertices.append(ICONVertex(Gf.Vec3d(0.0, 0.0, 1.0), [combined_diamond_idx(i, 0) for i in range(5)]))
    
    phi = np.deg2rad(-179)
    theta = np.arctan(0.5)
    step = np.deg2rad(72)
    
    # upper ring
    for i in range(5):
        icon_vertices.append(ICONVertex(
            Gf.Vec3d(
                np.cos(phi+i*step)*np.cos(theta), 
                np.sin(phi+i*step)*np.cos(theta), 
                np.sin(theta)), 
                [
                    combined_diamond_idx((i-1)%5,0), 
                    combined_diamond_idx((i-1)%5,1), 
                    combined_diamond_idx(i+5,0), 
                    combined_diamond_idx(i,0), 
                    combined_diamond_idx(i,1)]))

    # weirdo ring
    offset_idx = len(icon_vertices)
    for i in range(5):
        cur_pos = Gf.Slerp(0.5, 
                icon_vertices[offset_idx-5+((i+0)%5)].pos,
                icon_vertices[offset_idx-5+((i+1)%5)].pos)
        cur_pos[2] *= -1
        icon_vertices.append(ICONVertex(cur_pos, [
            combined_diamond_idx(i, 1),
            combined_diamond_idx(i+5, 0),
            combined_diamond_idx(i+5, 1),
            combined_diamond_idx((i+1)%5+5, 0)
            ]))

    # construct upper diamonds (idx 0 - 4)
    for i in range(5):
        icon_faces.append(ICONFace([0,(i)%5+1,(i+1)%5+1], combined_diamond_idx(i, 0), icon_vertices))
        icon_faces.append(ICONFace([offset_idx+i, (i+1)%5+1,(i)%5+1], combined_diamond_idx(i, 0), icon_vertices))
    
    # lower ring 
    theta = -np.arctan(0.5)
    for i in range(0,5):
        icon_vertices.append(ICONVertex(
            Gf.Vec3d(
                np.cos(phi+i*step)*np.cos(theta), 
                np.sin(phi+i*step)*np.cos(theta), 
                np.sin(theta)), 
                [
                    combined_diamond_idx(i+5,0), 
                    combined_diamond_idx(i+5,1), 
                    combined_diamond_idx((i-1)%5+5,1)]))

    # south pole
    icon_vertices.append(ICONVertex(Gf.Vec3d(0.0, 0.0,-1.0), [combined_diamond_idx(i, 1) for i in range(5,10)]))
    last = len(icon_vertices)-1

    # construct lower diamonds (idx 5 - 9)
    for i in range(5):
        #icon_faces.append(ICONFace(
        #    [i+1, offset_idx+(i-1)%5, offset_idx+(i+0)%5],
        #    combined_diamond_idx(i+5, 0), icon_vertices))
        #icon_faces.append(ICONFace([last,last-6+i%5+1,last-6+(i+1)%5+1], combined_diamond_idx(i+5, 1), icon_vertices))
        icon_faces.append(ICONFace(
            [i+1, offset_idx+(i-1)%5, last-6+i%5+1, offset_idx+(i+0)%5],
            combined_diamond_idx(i+5, 0), icon_vertices))
        icon_faces.append(ICONFace([last, last-6+i%5+1, offset_idx+(i+0)%5, last-6+(i+1)%5+1], combined_diamond_idx(i+5, 1), icon_vertices))

    return icon_vertices, icon_faces

class ICONHelper:
    def __init__(self, ext_id, scale=4950):
        self._ext_id = ext_id
        self._diamond_list = []
        self._icon_vertices, self._icon_faces = construct_icon_vertices()
        for i,v in enumerate(self._icon_vertices):
            self._icon_vertices[i].pos = v.pos*scale

        self._dynamic_diamonds_enabled = False
        self._viewport_subscription = None
        self._menu_entry = None

        self._dynamic_texture_interface = hpcvis.dynamictexture.acquire_dynamic_texture_interface()

        self._update_worker_task = None
        self._update_event = None

        viewport_api = get_active_viewport()
        if viewport_api is not None:
            self._enable_dynamic_diamonds()
            action_registry = omni.kit.actions.core.acquire_action_registry()
            action_registry.register_action(self._ext_id, 
                'iconhelper.dynamic_diamonds', self._toggle_dynamic_diamonds, 'DynamicDiamonds', 'Toggle dynamic loading of diamond textures')
            self._menu_entry = MenuItemDescription("ICON",
                    sub_menu=[MenuItemDescription("Dynamic Diamonds", ticked=True,
                        ticked_value=self.dynamic_diamonds_enabled,
                        onclick_action=(self._ext_id, 'iconhelper.dynamic_diamonds'))])
            add_menu_items([self._menu_entry], name="Rendering")

    async def _update_worker(self):
        while True:
            try:
                await self._update_event.wait()
                self._update_event.clear()
                self._update(get_active_viewport())
            except asyncio.CancelledError:
                carb.log_warn(f'Cancelled Task')
                break
            except Exception as e:
                carb.log_error(f'Exception triggered during dynamic diamond worker: {e}')

    @property
    def dynamic_diamonds_enabled(self):
        return self._dynamic_diamonds_enabled

    def _enable_dynamic_diamonds(self):
        if not self.dynamic_diamonds_enabled:
            viewport_api = get_active_viewport()
            if viewport_api is None:
                carb.log_warn(f'Tried enabling dynamic diamonds with no active viewport')
                return
            self._dynamic_diamonds_enabled = True
            if len(self._diamond_list) > 0:
                self._register_viewport_subscription()
                self._setup_worker()

    def _setup_worker(self):
        if self._update_worker_task is None:
            self._update_event = asyncio.Event()
            self._update_event.set()
            self._update_worker_task = async_engine.run_coroutine(self._update_worker())

    def _disable_dynamic_diamonds(self):
        if self.dynamic_diamonds_enabled:
            self._dynamic_diamonds_enabled = False
            for f, s in self._diamond_list:
                for i in range(10):
                    s[i].active = f.active
            if self._viewport_subscription is not None:
                self._viewport_subscription.destroy()
                self._viewport_subscription = None

    def _toggle_dynamic_diamonds(self):
        if self.dynamic_diamonds_enabled:
            self._disable_dynamic_diamonds()
        else:
            self._enable_dynamic_diamonds()

    def _register_viewport_subscription(self):
        if self._viewport_subscription is None:
            self._viewport_subscription = get_active_viewport().subscribe_to_view_change(self._on_view_change)
        if self._update_event is not None:
            self._update_event.set()
        else:
            self._setup_worker()

    def __del__(self):
        #self._stage_event_sub.unsubscribe()
        self._disable_dynamic_diamonds()
        self._diamond_list = []
        if self._menu_entry is not None:
            remove_menu_items(self._menu_entry, name="Rendering")
            self._menu_entry = None

    def register_diamond_list(self, feature, diamond_list):
        self._diamond_list.append((feature, diamond_list))

        if len(self._diamond_list) == 1 and self._dynamic_diamonds_enabled:
            # first entry
            self._register_viewport_subscription()

    def is_registered(self, tex):
        # TODO: I don't think that makes sense anymore, _diamond_list is a list of pairs of feature,diamond_list
        return tex in self._diamond_list

    def unregister_diamond_list(self, feature, diamond_list):
        if diamond_list is None:
            self._diamond_list = []
            return

        #for d in diamond_list:
        #    self._diamond_list.remove(diamond_list)
        self._diamond_list.remove((feature, diamond_list))

        if len(self._diamond_list) == 0:
            # no entries left
            if self._viewport_subscription is not None:
                self._viewport_subscription.destroy()
                self._viewport_subscription = None

    def get_icon_faces_to_screen_space(self, viewport_api):
        # get camera transform
        world_to_ndc = viewport_api.world_to_ndc
        vertices_in_ndc_space = [world_to_ndc.Transform(v.pos)[:2] for v in self._icon_vertices]

        icon_polygons = [Polygon([vertices_in_ndc_space[j] for j in f.indices]) for f in self._icon_faces]
        for p in icon_polygons:
            p.clip_to_range(-1,1,-1,1)

        icon_polygon_areas = np.array([p.get_area() for p in icon_polygons])

        cam_dir = Gf.Vec3d(*viewport_api.transform.GetRow(2)[:3])
        facing_ratios = np.array([Gf.Dot(f.face_normal, cam_dir) for f in self._icon_faces])

        icon_face_diamonds = [diamond_idx_from_combined(f.diamond)[0] for f in self._icon_faces]
        score = (icon_polygon_areas*facing_ratios).reshape((-1,2)).sum(axis=1)
        order = np.flip(np.argsort(score))

        # TODO: the polygons we currently use are a rough approximation and can 
        # reach 0 projected area even when the diamond is in view. so we should use 
        # a better heuristic and better polygonial approximation in the future
        active_diamonds = score > 1e-4 # NOTE: arbitrary threshold

        #dynamic_textures = [t.target_url for t in self._dynamic_texture_interface.list()]
        #carb.log_error(f'Dynamic Textures: {dynamic_textures}')
        #for i in range(10):
        #    for f, s in self._diamond_list:
        #        if s[i].target_url in dynamic_textures:
        #            s[i].active = active_diamonds[i] and f.active
        #        else:
        #            carb.log_warn(f'Unregistering stale dynamic texture {s[i].target_url}')
        #            self.unregister_diamond_list(f, s)
        for i in range(10):
            for f, s in self._diamond_list:
                s[i].active = active_diamonds[i] and f.active
    
    def _on_view_change(self, viewport_api):
        if self._update_event is not None:
            self._update_event.set()

    def _update(self, viewport_api):
        try:
            self.get_icon_faces_to_screen_space(viewport_api)
        except Exception as e:
            carb.log_error(e)
            import traceback
            traceback.print_exc()

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

# We create a mesh with UV coordinates so we can map ICON Diamonds
# NOTE: This unfortunately doesn't work perfectly as there can be optimization
# steps on those grids. We could process the ICON grids directly from the NetCDF
# files but I've found that it's not trivial to find the right UV coordinates
# for the vertices from the per-diamond cell indices, mainly due to the many
# edge cases and the 'split' diamonds along the equator

import numpy as np
from pxr import Usd, UsdGeom, Sdf, Gf, Tf, Vt
#import omni.usd

num_subds = 4

def refine_mesh(verts, tris, sts):
    # TODO: subdivide each triangle and build new verts,tris arrays
    num_verts = verts.shape[0]
    num_tris = len(tris)//3
    num_new_tris = num_tris*4
    print(f'Num Triangles: {num_tris}')
    split_verts_dict = {}

    def spherical_split(verts, a, b):
        return Gf.Slerp(0.5,
                Gf.Vec3d(verts[a,0], verts[a,1], verts[a,2]),
                Gf.Vec3d(verts[b,0], verts[b,1], verts[b,2]))
        #return (
        #        Gf.Vec3d(verts[a,0], verts[a,1], verts[a,2]) +
        #        Gf.Vec3d(verts[b,0], verts[b,1], verts[b,2])).GetNormalized()
    def get_key(a, b):
        return (a,b) if a<=b else (b,a)

    # create pessimistic array of verts (no edge shared)
    new_verts = np.empty_like(verts, shape=(num_new_tris*3, 3))
    # add 'old' verts to beginning of array
    new_verts[0:num_verts,:] = verts
    new_verts_offset = num_verts

    # create pessimistic array of sts (no edge shared)
    new_sts = np.empty_like(verts, shape=(num_new_tris*3, 2))
    # add 'old' verts to beginning of array
    new_sts[0:num_verts,:] = sts

    new_tris = np.empty_like(tris, shape=(num_new_tris*3))

    #refined_idxs = np.empty_like(tris, shape=(6))
    refined_idxs = np.full_like(tris, np.nan, shape=(6))
    for cur_tri_idx in range(num_tris):
        a,b,c = tris[cur_tri_idx*3:cur_tri_idx*3+3]
        refined_idxs[0:3] = tris[cur_tri_idx*3:cur_tri_idx*3+3]

        # for each edge, split spherically and add midpoint verts
        for i,j in [(a,b), (b,c), (c,a)]:
            if get_key(i,j) not in split_verts_dict:
                IJ = spherical_split(verts, i, j)
                new_verts[new_verts_offset] = IJ
                new_sts[new_verts_offset] = [
                        0.5*(sts[i,0] + sts[j,0]),
                        0.5*(sts[i,1] + sts[j,1])]
                split_verts_dict[get_key(i,j)] = new_verts_offset
                new_verts_offset += 1
        refined_idxs[3] = split_verts_dict[get_key(a,b)]
        refined_idxs[4] = split_verts_dict[get_key(b,c)]
        refined_idxs[5] = split_verts_dict[get_key(c,a)]

        tri_base_idx = cur_tri_idx*4
        pattern = [
                0,3,5,
                3,1,4,
                3,4,5,
                5,4,2]
        for i,j in enumerate(pattern):
            new_tris[tri_base_idx*3+i] = refined_idxs[j]
    new_verts.resize((new_verts_offset,3))
    new_sts.resize((new_verts_offset,2))
    return new_verts, new_tris, new_sts

# create vertices
ico_verts = np.ndarray((42, 3))
phi_shift = np.deg2rad(1 - 180.0)

# poles
ico_verts[0 ,:] = [0, 0,+1]
ico_verts[41 ,:] = [0, 0,-1]
idx_offset = 1

# first ring
ring1_size = 5
ring1_offset = idx_offset
theta_offset = (np.pi/2+np.arctan(0.5))/2
ico_verts[idx_offset:idx_offset+5,:] = [[ \
            np.cos(x*2*np.pi/5+phi_shift)*np.cos(theta_offset),
            np.sin(x*2*np.pi/5+phi_shift)*np.cos(theta_offset),
            np.sin(theta_offset)] for x in range(5)]
idx_offset += ring1_size

# second ring
ring2_size = 10
ring2_offset = idx_offset
theta_offset = +np.arctan(0.5)#+np.arctan(0.500566)
# TODO: rearrange to remove tmp
tmp = np.asarray([[ \
            np.cos(x*2*np.pi/5+phi_shift)*np.cos(theta_offset),
            np.sin(x*2*np.pi/5+phi_shift)*np.cos(theta_offset),
            np.sin(theta_offset)] for x in range(5)])
for i in range(5):
    ico_verts[idx_offset+i*2,:] = tmp[i]
# NOTE: the vertices are not distributed along a circle, it's a 5 vertex circle with one subdivision
#norm_factor = np.sqrt(5/(8*np.cos(2*np.pi/5) + 12))
for i in range(5):
    #ico_verts[idx_offset+i*2+1,:] = (tmp[i]+tmp[(i+1)%5])*norm_factor
    ico_verts[idx_offset+i*2+1,:] = Gf.Slerp(0.5, Gf.Vec3d(*tmp[i]), Gf.Vec3d(*tmp[(i+1)%5]))
idx_offset += ring2_size

# TODO: that one is difficult! This really is a ring of vertices from a subvidision
#       so we need to identify the vertices of the edges that we want to split
# equator ring
ring3_size = 10
ring3_offset = idx_offset
theta_offset = 0
cor_angle = np.deg2rad(0.6)
ico_verts[idx_offset:idx_offset+10,:] = [[ \
            np.cos((x+0.5)*2*np.pi/10+phi_shift-cor_angle+2*cor_angle*(x%2==0))*np.cos(theta_offset),
            np.sin((x+0.5)*2*np.pi/10+phi_shift-cor_angle+2*cor_angle*(x%2==0))*np.cos(theta_offset),
            np.sin(theta_offset)] for x in range(10)]
#def mirror_z(v):
#    return type(v)(v[0], v[1], -v[2])
#for i in range(10):
#    if i%2 == 0:
#        ico_verts[idx_offset+i,:] = Gf.Slerp(0.5,
#                Gf.Vec3d(*ico_verts[ring2_offset+(i+0)%10]),
#                mirror_z(Gf.Vec3d(*ico_verts[ring2_offset+(i+1)%10])))
#    else:
#        ico_verts[idx_offset+i,:] = Gf.Slerp(0.5,
#                Gf.Vec3d(*ico_verts[ring2_offset+(i+1)%10]),
#                mirror_z(Gf.Vec3d(*ico_verts[ring2_offset+(i+0)%10])))
idx_offset += ring3_size

# forth ring
ring4_size = 10
ring4_offset = idx_offset
ico_verts[idx_offset:idx_offset+10,:] = ico_verts[ring2_offset:ring2_offset+10,:]
ico_verts[idx_offset:idx_offset+10,2] *= -1
idx_offset += ring4_size

# fifth ring
ring5_size = 5
ring5_offset = idx_offset
ico_verts[idx_offset:idx_offset+5,:] = ico_verts[ring1_offset:ring1_offset+5,:]
ico_verts[idx_offset:idx_offset+5,2] *= -1
idx_offset += ring5_size

print(ico_verts)
print(idx_offset)

stage = Usd.Stage.CreateNew('/tmp/diamond_globe.usd')
UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
xform = UsdGeom.Xform.Define(stage, '/globe')
stage.SetDefaultPrim(xform.GetPrim())
#
#points = UsdGeom.Points.Define(stage, xform.GetPath().AppendChild('points'))
#points.GetPointsAttr().Set(ico_verts)
#points.SetWidthsInterpolation(UsdGeom.Tokens.constant)
#points.GetWidthsAttr().Set([5/200])

# Upper Diamond Parts of Upper Diamonds
for i in range(5):
    base_offset = i
    diamond_verts = np.vstack([
            ico_verts[0,:],
            ico_verts[ring1_offset+((i*1)+0)%ring1_size,:],
            ico_verts[ring1_offset+((i*1)+1)%ring1_size,:],
            ico_verts[ring2_offset+((i*2)+0)%ring2_size,:],
            ico_verts[ring2_offset+((i*2)+1)%ring2_size,:],
            ico_verts[ring2_offset+((i*2)+2)%ring2_size,:]
            ])
    diamond_idxs = np.array([
            0, 1, 2,
            1, 3, 4,
            1, 4, 2,
            2, 4, 5,
            ])
    sts = np.array([
            (0.0, 1.0),
            (0.0, 0.5),
            (0.5, 1.0),
            (0.0, 0.0),
            (0.5, 0.5),
            (1.0, 1.0),
            ], dtype=np.float64)

    for j in range(num_subds):
        diamond_verts, diamond_idxs, sts = refine_mesh(diamond_verts, diamond_idxs, sts)
    #diamond_verts /= np.linalg.norm(diamond_verts, axis=1).reshape(-1,1)

    mesh = UsdGeom.Mesh.Define(stage, xform.GetPath().AppendChild(f'diamond_{i}_u'))
    mesh.GetPointsAttr().Set(diamond_verts)
    mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(len(diamond_idxs)//3,3))
    mesh.GetFaceVertexIndicesAttr().Set(diamond_idxs)
    primvarsAPI = UsdGeom.PrimvarsAPI(mesh)
    primvarsAPI.CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(sts)
    primvarsAPI.CreatePrimvar('diamond_idx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(i)
    primvarsAPI.CreatePrimvar('diamond_subidx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(0)
# Lower Diamond Parts of Upper Diamonds
for i in range(5):
    base_offset = i
    diamond_verts = np.vstack([
            ico_verts[ring2_offset+((i*2)+0)%ring2_size,:],
            ico_verts[ring2_offset+((i*2)+1)%ring2_size,:],
            ico_verts[ring2_offset+((i*2)+2)%ring2_size,:],
            ico_verts[ring3_offset+((i*2)+0)%ring3_size,:],
            ico_verts[ring3_offset+((i*2)+1)%ring3_size,:],
            ico_verts[ring4_offset+((i*2)+1)%ring4_size,:],
            ])
    diamond_idxs = np.array([
            0, 3, 1,
            1, 3, 4,
            2, 1, 4,
            3, 5, 4,
            ])
    sts = np.array([
            (0.0, 0.0),
            (0.5, 0.5),
            (1.0, 1.0),
            (0.5, 0.0),
            (1.0, 0.5),
            (1.0, 0.0),
            ], dtype=np.float64)

    for j in range(num_subds):
        diamond_verts, diamond_idxs, sts = refine_mesh(diamond_verts, diamond_idxs, sts)
    #diamond_verts /= np.linalg.norm(diamond_verts, axis=1).reshape(-1,1)

    mesh = UsdGeom.Mesh.Define(stage, xform.GetPath().AppendChild(f'diamond_{i}_l'))
    mesh.GetPointsAttr().Set(diamond_verts)
    mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(len(diamond_idxs)//3,3))
    mesh.GetFaceVertexIndicesAttr().Set(diamond_idxs)
    primvarsAPI = UsdGeom.PrimvarsAPI(mesh)
    primvarsAPI.CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(sts)
    primvarsAPI.CreatePrimvar('diamond_idx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(i)
    primvarsAPI.CreatePrimvar('diamond_subidx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(1)
# Upper Diamond Parts of Lower Diamonds
for i in range(5):
    base_offset = i
    diamond_verts = np.vstack([
            ico_verts[ring2_offset+((i*2)+0)%ring2_size,:],
            ico_verts[ring3_offset+((i*2)-1)%ring3_size,:],
            ico_verts[ring3_offset+((i*2)+0)%ring3_size,:],
            ico_verts[ring4_offset+((i*2)-1)%ring4_size,:],
            ico_verts[ring4_offset+((i*2)+0)%ring4_size,:],
            ico_verts[ring4_offset+((i*2)+1)%ring4_size,:],
            ])
    diamond_idxs = np.array([
            0, 1, 2,
            1, 3, 4,
            1, 4, 2,
            2, 4, 5,
            ])
    sts = np.array([
            (0.0, 1.0),
            (0.0, 0.5),
            (0.5, 1.0),
            (0.0, 0.0),
            (0.5, 0.5),
            (1.0, 1.0),
            ], dtype=np.float64)

    for j in range(num_subds):
        diamond_verts, diamond_idxs, sts = refine_mesh(diamond_verts, diamond_idxs, sts)
    #diamond_verts /= np.linalg.norm(diamond_verts, axis=1).reshape(-1,1)

    mesh = UsdGeom.Mesh.Define(stage, xform.GetPath().AppendChild(f'diamond_{i+5}_u'))
    mesh.GetPointsAttr().Set(diamond_verts)
    mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(len(diamond_idxs)//3,3))
    mesh.GetFaceVertexIndicesAttr().Set(diamond_idxs)
    primvarsAPI = UsdGeom.PrimvarsAPI(mesh)
    primvarsAPI.CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(sts)
    primvarsAPI.CreatePrimvar('diamond_idx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(i+5)
    primvarsAPI.CreatePrimvar('diamond_subidx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(0)
# Lower Diamond Parts of Lower Diamonds
for i in range(5):
    base_offset = i
    diamond_verts = np.vstack([
            ico_verts[ring4_offset+((i*2)+0)%ring4_size,:],
            ico_verts[ring4_offset+((i*2)+1)%ring4_size,:],
            ico_verts[ring4_offset+((i*2)+2)%ring4_size,:],
            ico_verts[ring5_offset+((i*1)+0)%ring5_size,:],
            ico_verts[ring5_offset+((i*1)+1)%ring5_size,:],
            ico_verts[-1,:],
            ])
    diamond_idxs = np.array([
            0, 3, 1,
            1, 3, 4,
            2, 1, 4,
            3, 5, 4,
            ])
    sts = np.array([
            [0.0, 0.0],
            [0.5, 0.5],
            [1.0, 1.0],
            [0.5, 0.0],
            [1.0, 0.5],
            [1.0, 0.0]
            ], dtype=np.float64)

    for j in range(num_subds):
        diamond_verts, diamond_idxs, sts = refine_mesh(diamond_verts, diamond_idxs, sts)
    #diamond_verts /= np.linalg.norm(diamond_verts, axis=1).reshape(-1,1)

    mesh = UsdGeom.Mesh.Define(stage, xform.GetPath().AppendChild(f'diamond_{i+5}_l'))
    mesh.GetPointsAttr().Set(diamond_verts)
    mesh.GetFaceVertexCountsAttr().Set(Vt.IntArray(len(diamond_idxs)//3,3))
    mesh.GetFaceVertexIndicesAttr().Set(diamond_idxs)
    primvarsAPI = UsdGeom.PrimvarsAPI(mesh)
    primvarsAPI.CreatePrimvar('st', Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex).Set(sts)
    primvarsAPI.CreatePrimvar('diamond_idx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(i+5)
    primvarsAPI.CreatePrimvar('diamond_subidx', Sdf.ValueTypeNames.Int, UsdGeom.Tokens.constant).Set(1)

stage.Save()

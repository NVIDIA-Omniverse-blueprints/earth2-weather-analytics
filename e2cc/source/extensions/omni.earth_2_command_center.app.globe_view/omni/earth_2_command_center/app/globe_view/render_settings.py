# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


import carb.settings

def set_render_settings():
    settings = carb.settings.get_settings()
    settings.set_int("/persistent/app/viewport/displayOptions", 0)
    
    settings.set_string("/rtx/rendermode", "rtx") #"PathTracing"
    # for atmosphere
    settings.set_int("/rtx/translucency/maxRefractionBounces", 3)
    settings.set_float("/rtx/translucency/worldEps", 0.0)
    #settings.set_bool("/rtx/newDenoiser/enabled", False)
    settings.set_bool("/rtx/directLighting/sampledLighting/enabled", True)
    #settings.set_int("/rtx/directLighting/sampledLighting/samplesPerPixel", 128)
    settings.set_bool("/rtx/ecoMode/enabled", True) # to avoid 'burn in' artifacts from DLSS
    settings.set_int("/rtx/post/aa/op", 3) # 0=None, 2=FXAA, 3=DLSS, 4=DLAA
    # don't do next frame prediction as we get bad artifacts when tumbling the globe
    settings.set_int("/rtx-transient/dlssg/enabled", False)
    # sometimes accumulation looks very blurry, we prefer flickering over blurring
    #settings.set_int("/rtx/lightspeed/render/enableAccumulation", False)
    
    # to avoid artifacts on the Globe
    settings.set_bool("/rtx/indirectDiffuse/enabled", False)
    settings.set_bool("/rtx/ambientOcclusion/enabled", False)
    
    settings.set_int("/rtx/pathtracing/spp", 1)
    settings.set_int("/rtx/pathtracing/totalSpp", 512)
    
    # caching seems to cause artifacts
    settings.set_bool("/rtx/pathtracing/cached.enabled", False)
    settings.set_bool("/rtx/resetPtAccumOnAnimTimeChange", True)
    
    # add film grain to help avoid banding artifacts from stream compression
    #settings.set_bool("/rtx/post/tvNoise/enabled", True)
    #settings.set_bool("/rtx/post/tvNoise/enableFilmGrain", True)
    #settings.set_float("/rtx/post/tvNoise/grainAmount", 0.01)
    
    # add motion blur
    settings.set_bool("/rtx/post/motionblur/enabled", True)
    settings.set_float("/rtx/post/motionblur/maxBlurDiameterFraction", 0.005)
    settings.set_int("/rtx/post/motionblur/numSamples", 16)

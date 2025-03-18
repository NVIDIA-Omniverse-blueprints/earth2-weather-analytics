# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


from typing import Literal

# Core typing definition. Only used for type validation

Float2 = tuple[float, float]
Float3 = tuple[float, float, float]

RangeF1D = tuple[float, float]
RangeF2D = tuple[Float2, Float2]
RangeF3D = tuple[Float3, Float3]

Int2 = tuple[int, int]
Int3 = tuple[int, int, int]

RangeI1D = tuple[int, int]
RangeI2D = tuple[Int2, Int2]
RangeI3D = tuple[Int3, Int3]

ColorRGB = tuple[float, float, float]
ColorRGBA = tuple[float, float, float, float]

FileFormatType = Literal["vdb"] | Literal["nvdb"]
ShaderSamplerType = Literal["float"] | Literal["Fp8"] | Literal["Fp16"] | Literal["FpN"]

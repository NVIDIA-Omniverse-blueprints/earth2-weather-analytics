# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.
import sys
import os
import carb

try:
    pydantic_keys = [k for k in sys.modules.keys() if k.startswith("pydantic")]
    for k in pydantic_keys:
        del sys.modules[k]
    try:
        del sys.modules["typing_extensions"]
    except:
        pass

    # And now shuffle the sys path to get the desired result
    for e in sys.path[:]:
        if "dfm" in e:
            sys.path.insert(0, e)
except:
    carb.log_warn("Error in dfm init with pydantic loading, if this is a test run, probably okay")

module_dir = os.path.dirname(os.path.abspath(__file__))
prebundle_path = os.path.abspath(os.path.join(module_dir, "../../../../pip_prebundle"))
if os.path.isdir(prebundle_path) and prebundle_path not in sys.path:
    sys.path.insert(0, prebundle_path)

# Import extension implementation
from .extension import *

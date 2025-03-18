# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



class ReferenceManager:
    def __singleton_init__(self):
        # Globe Scene
        self.__scene = None
        self.__ui = None

    def __new__(cls):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
            cls._instance.__singleton_init__()
        return cls._instance

    @property
    def globe_scene(self) -> "GlobeScene":
        return self.__scene

    @globe_scene.setter
    def globe_scene(self, scene):
        self.__scene = scene

    @property
    def globe_ui(self) -> "GlobeUI":
        return self.__ui

    @globe_ui.setter
    def globe_ui(self, interface):
        self.__ui = interface

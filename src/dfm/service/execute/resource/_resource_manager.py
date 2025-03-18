# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Optional
from dfm.config.resource import ResourceConfigs


class ResourceManager:
    """
    The ResourceManager is responsible for managing resources for a site.
    """

    def __init__(self, site: Any, config: Optional[ResourceConfigs]):
        """
        Initialize the ResourceManager.

        Args:
            site: The site to manage resources for.
            config: The configuration for the site.
        """
        self._site = site
        self._config = config

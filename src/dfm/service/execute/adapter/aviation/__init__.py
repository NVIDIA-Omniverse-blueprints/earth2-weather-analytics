# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

"""Aviation weather analytics adapter implementations."""
from ._compute_wind_shear import ComputeWindShear  # noqa: F401
from ._compute_ellrod_index import ComputeEllrodIndex  # noqa: F401
from ._compute_icing_probability import ComputeIcingProbability  # noqa: F401
from ._compute_crosswind import ComputeCrosswind  # noqa: F401
from ._load_metar_data import LoadMetarData  # noqa: F401
from ._load_taf_data import LoadTafData  # noqa: F401
from ._load_pirep_data import LoadPirepData  # noqa: F401
from ._load_sigmet_data import LoadSigmetData  # noqa: F401
from ._extract_route_weather import ExtractRouteWeather  # noqa: F401
from ._score_route_hazards import ScoreRouteHazards  # noqa: F401

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

from typing import Any, Dict
import xarray
from datetime import datetime, timedelta, timezone
from enum import Enum
from dataclasses import dataclass
import dateutil.parser

from herbie import Herbie

import numpy as np

from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider, HrrrProvider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.data_loader import LoadHrrrModelData as LoadHrrrModelDataParams
from dfm.config.adapter.data_loader import LoadHrrrData as LoadHrrrDataConfig
from dfm.service.execute.discovery import (
    field_advisor,
    AdvisedOneOf,
    AdvisedLiteral,
    AdvisedDateRange,
    AdvisedSubsetOf,
)

from ._xarray_loader_caching_iterator import XarrayLoaderCachingIterator


class HrrrProduct(Enum):
    """
    Enum representing different HRRR product types:
    - SFC: Surface products (2m temperature, 10m winds, etc)
    - PRS: Pressure level products (temperature, winds at different pressure levels)
    - NAT: Native model level products
    - SUBH: Sub-hourly products
    """

    SFC = "sfc"
    PRS = "prs"
    NAT = "nat"
    SUBH = "subh"


class HrrrPhase(Enum):
    """
    Enum representing different HRRR data phases:
    - ANALYSIS: Analysis phase ('anl') - represents the current state
    - FORECAST: Forecast phase ('fct') - represents predicted future states
    - BOTH: Both analysis and forecast phases ('both')
    """

    ANALYSIS = "anl"
    FORECAST = "fct"
    BOTH = "both"


@dataclass
class HrrrDataRequest:
    """
    Data class representing mapping from ERA5-style variable to HRRR-style variable.

    Attributes:
        product: The HRRR product type (surface, pressure level, etc)
        search_string: String pattern to search for in HRRR variable names
        fxx: Forecast hour (0 for analysis, >0 for forecast)
        hrrr_var: The HRRR variable name
    """

    product: HrrrProduct
    search_string: str
    fxx: int
    hrrr_var: str


def generate_era5_to_hrrr_variables():
    """
    Generates a mapping between ERA5 variable names and corresponding HRRR data requests.

    This function creates a dictionary that maps ERA5 variable names to HrrrDataRequest objects,
    which contain the necessary information to fetch equivalent data from HRRR datasets.

    The mapping includes:
    1. Surface variables like wind components (u10m, v10m), temperature (t2m),
       surface pressure (sp), etc.
    2. Pressure level variables for multiple atmospheric levels (50-1000mb) including:
       - Wind components (u, v)
       - Geopotential height (z)
       - Temperature (t)
       - Specific humidity (q)

    Returns:
        dict: A dictionary mapping ERA5 variable names to HrrrDataRequest objects.
              Some variables may map to None if no equivalent exists in HRRR.
    """
    # Surface variables
    variables = {
        "u10m": HrrrDataRequest(
            HrrrProduct.SFC, "UGRD:10 m above", HrrrPhase.BOTH, "u10"
        ),
        "v10m": HrrrDataRequest(
            HrrrProduct.SFC, "VGRD:10 m above", HrrrPhase.BOTH, "v10"
        ),
        "u100m": None,
        "v100m": None,
        "t2m": HrrrDataRequest(HrrrProduct.SFC, "TMP:2 m above", HrrrPhase.BOTH, "t2m"),
        "sp": HrrrDataRequest(HrrrProduct.SFC, "PRES:surface", HrrrPhase.BOTH, "sp"),
        "msl": HrrrDataRequest(HrrrProduct.SFC, "MSLMA", HrrrPhase.BOTH, "mslma"),
        "tcwv": HrrrDataRequest(HrrrProduct.SFC, "PWAT", HrrrPhase.BOTH, "pwat"),
    }

    # Pressure level variables
    pressure_levels = [50, 100, 150, 200, 250, 300, 400, 500, 600, 700, 850, 925, 1000]

    var_mappings = {
        "u": ("UGRD", "u"),  # (HRRR search string prefix, HRRR variable name)
        "v": ("VGRD", "v"),
        "z": ("HGT", "gh"),
        "t": ("TMP", "t"),
        "q": ("SPFH", "q"),
    }

    # Generate pressure level variables
    for var, (search_prefix, hrrr_var) in var_mappings.items():
        for level in pressure_levels:
            era5_name = f"{var}{level}"
            search_string = f"{search_prefix}:{level} mb"
            variables[era5_name] = HrrrDataRequest(
                HrrrProduct.PRS, search_string, HrrrPhase.BOTH, hrrr_var
            )

    return variables


class LoadHrrrData(
    NullaryAdapter[Provider, LoadHrrrDataConfig, LoadHrrrModelDataParams]
):
    """
    Adapter to load HRRR data from the HRRR provider.

    This adapter provides functionality to load HRRR data based on user-specified parameters.
    It supports both surface and pressure level data.

    The adapter supports the following parameters:
    - time: The start time of the data to load
    - step: The forecast step to load
    - variables: The variables to load

    The adapter will load the data for the specified time and step, and return a dataset
    containing the requested variables.
    """

    DATE_FORMAT = "%Y-%m-%dT%H:00"
    ERA5_TO_HRRR_VARIABLES = generate_era5_to_hrrr_variables()

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: HrrrProvider,
        config: LoadHrrrDataConfig,
        params: LoadHrrrModelDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        return self._collect_local_hash_dict_helper(
            time=self.params.time,
            step=self.params.step,
            variables=self.params.variables,
        )

    def _instantiate_caching_iterator(self):
        cache_fsspec_conf = self.provider.cache_fsspec_conf()
        self._logger.debug("Cache fsspec config: %s", cache_fsspec_conf)
        if cache_fsspec_conf:
            self._logger.info(
                "Instantiating caching iterator with cache_fsspec_conf: %s",
                cache_fsspec_conf,
            )
            return XarrayLoaderCachingIterator(self, cache_fsspec_conf)
        return None

    @field_advisor("variables", order=0)
    async def available_variables(self, _value, _context):
        return AdvisedOneOf([AdvisedLiteral("*"), AdvisedSubsetOf(LoadHrrrData.ERA5_TO_HRRR_VARIABLES.keys())])  # type: ignore

    @field_advisor("time", order=1)
    async def available_time(self, _value, _context):
        # Conservatively advise time two hors earlier
        end = datetime.now(timezone.utc) - timedelta(hours=2)
        # Break the tree here - we can't figure out allowed step values without time
        return AdvisedDateRange("2014-07-30T00:00", end.strftime(self.DATE_FORMAT), break_on_advice=True)  # type: ignore

    @field_advisor("step", order=2)
    async def available_step(self, _value, _context):
        t = _context.get("time")
        if not t:
            raise ValueError(f"Unexpected time file in discovery: {t}")
        t = datetime.strptime(t, self.DATE_FORMAT)
        max_step = 48 if t.hour % 6 == 0 else 18
        return AdvisedOneOf([AdvisedLiteral(str(i)) for i in range(0, max_step + 1)])

    def body(self) -> Any:
        # Parse the time parameter
        try:
            time = dateutil.parser.parse(self.params.time)
        except dateutil.parser.ParserError:
            raise ValueError(f"Invalid start time {self.params.time}.")
        # Get forecast step and validate it's within allowed range [0,48]
        step = self.params.step
        if step < 0 or step > 48:
            raise ValueError(f"Step value {step} outside of required range [0, 48].")

        # Get list of variables to load - either all valid variables if '*' is specified,
        # or use the explicitly provided list of variables
        variables = self.params.variables
        if isinstance(variables, str) and variables == "*":
            candidates = [
                var
                for var, mapping in LoadHrrrData.ERA5_TO_HRRR_VARIABLES.items()
                if mapping is not None
            ]
        else:
            candidates = variables
        # Split variables into surface and pressure level products based on product field in mapping
        sfc_variables = []
        prs_variables = []
        for var in candidates:
            hrrr_mapping = LoadHrrrData.ERA5_TO_HRRR_VARIABLES.get(var)
            if not hrrr_mapping:
                raise ValueError(f"No HRRR mapping found for ERA5 variable: {var}")
            var_list = (
                sfc_variables
                if hrrr_mapping.product == HrrrProduct.SFC
                else prs_variables
            )
            var_list.append(var)

        if not sfc_variables and not prs_variables:
            raise ValueError("No valid variables specified")

        self._logger.info("Surface variables: %s", sfc_variables)
        self._logger.info("Pressure level variables: %s", prs_variables)

        # Now group variables by their search strings to minimize file reads
        # and load the data for each search string into a separate data array.
        # We do it to avoid running into issues with different hypercubes.
        dataarrays = []
        for variables in [sfc_variables, prs_variables]:
            if not variables:
                continue
            # Open file for product and step
            herbie_args = {
                "date": time,
                "model": "hrrr",
                # All variables in the list have the same product
                "product": LoadHrrrData.ERA5_TO_HRRR_VARIABLES.get(
                    variables[0]
                ).product.value,
                "fxx": step,
            }
            cache_fsspec_conf = self.provider.cache_fsspec_conf()
            if cache_fsspec_conf:
                herbie_args["save_dir"] = cache_fsspec_conf.base_url
            hr = Herbie(**herbie_args)
            # Now we can read variables from this product.
            search_groups = {}
            for var in variables:
                # Group variables by their search strings to minimize file reads
                hrrr_mapping = LoadHrrrData.ERA5_TO_HRRR_VARIABLES.get(var)
                search = hrrr_mapping.search_string
                if search not in search_groups:
                    search_groups[search] = []
                search_groups[search].append(var)
            # Read data for each search string into a separate data array.
            for search, vars in search_groups.items():
                self._logger.info("Using search group: %s", search)
                ds = hr.xarray(
                    search=search,
                    remove_grib=False,
                )
                if isinstance(ds, list):
                    raise ValueError(
                        "Selected variables belong to different hypercubes."
                    )
                for var in vars:
                    hrrr_var = LoadHrrrData.ERA5_TO_HRRR_VARIABLES.get(var).hrrr_var
                    dataarrays.append(ds.get(hrrr_var).rename(var))

        # Merge data arrays into a single dataset
        # Create new dataset with coordinates from first data array
        first_da = dataarrays[0]
        ds = xarray.Dataset(
            coords={
                "time": first_da.time + first_da.step,
                "step": first_da.step,
                "lat": first_da.latitude,
                "lon": first_da.longitude,
                "valid_time": first_da.time + first_da.step,
                "gribfile_projection": first_da.gribfile_projection,
            }
        )

        # Add each data array to the dataset
        for da in dataarrays:
            ds[da.name] = da

        hrrr_crs = ds.herbie.crs
        ds.rio.write_crs(hrrr_crs)

        # set x and y as explicit coordinates. The herbie dataset mentions x and y dimensions but doesn't have coordinate arrays for them
        # Those numbers are "semi-magic", they are what the hrrr data contains when you download it without herbie. Since HRRR is very
        # localized it's okay to hard-code I think
        xcoords = np.linspace(-2697520.142521929, 2696479.857478071, 1799)
        ycoords = np.linspace(-1587306.152556665, 1586693.847443335, 1059)
        ds.coords["x"] = xcoords
        ds.coords["y"] = ycoords

        as_wgs84 = ds.rio.reproject(4326)
        # Rename x and y back to lon and lat
        as_wgs84 = as_wgs84.rename({"x": "longitude", "y": "latitude"})
        # Remove some variables that are not needed
        as_wgs84 = as_wgs84.drop_vars(
            [
                "time",
                "heightAboveGround",
                "atmosphereSingleLayer",
                "valid_time",
                "gribfile_projection",
                "step",
            ],
            errors="ignore",
        )

        # Expand the dataset along the 'time' dimension
        # And shift longitudes into positive space
        as_wgs84 = as_wgs84.assign_coords(
            time=ds["time"].data, longitude=(as_wgs84.longitude % 360)
        ).expand_dims(dim="time")

        self._logger.info("Loaded dataset %s", as_wgs84)
        return as_wgs84

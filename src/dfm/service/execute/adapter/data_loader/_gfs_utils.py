"""Download GFS data"""

# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES.
# SPDX-FileCopyrightText: All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
import datetime
import hashlib
import os
import pathlib
import shutil
import argparse
from typing import List, Dict, Tuple, Union, Literal, Callable
import logging
import dask

import boto3
import botocore
import numpy as np
import s3fs
import xarray as xr
from botocore import UNSIGNED
from ._channels import ERA5_CHANNELS, ERA5_TO_GFS_S3_MAP


def call_download_s3_grib_cached(gfs, grib_file_name, byte_offset, byte_length):
    """Making this a top level function because the ProcessPool requires that
    for pickling"""
    return gfs.download_s3_grib_cached(grib_file_name, byte_offset, byte_length)


class GFS:
    """The global forecast service (GFS) initial state data source provided on an
    equirectangular grid.

    Parameters
    ----------
    cache : bool, optional
        Cache data source on local memory, by default False
    verbose : bool, optional
        Print download progress, by default True
    """

    MAX_BYTE_SIZE = 5000000

    GFS_LAT = np.linspace(90, -90, 721)
    GFS_LON = np.linspace(0, 359.75, 1440)

    def __init__(
        self,
        bucket_name: str,
        cache_folder: str,
        concurrency: Literal["async_proc_pool", "dask", "none"] = "async_proc_pool",
        num_processes: int = 4,  # for async proc pool
        keep_cache: bool = False,
        verbose: bool = True,
        read_timeout: int = 60,
        connect_timeout: int = 120,
    ):
        self._bucket_name = bucket_name
        self._cache_folder = cache_folder
        self._concurrency = concurrency
        self._num_processes = num_processes
        self._keep_cache = keep_cache
        self._verbose = verbose
        self.read_timeout = read_timeout
        self.connect_timeout = connect_timeout

    async def __call__(
        self,
        time: Union[datetime.datetime, List[datetime.datetime]],
        variables,
    ) -> xr.DataArray:
        """Retrieve GFS initial data to be used for initial conditions for the given
        time, channel information, and optional history.

        Parameters
        ----------
        time : Union[datetime.datetime, list[datetime.datetime]]
            Timestamps to return data for (UTC).

        Returns
        -------
        xr.DataArray
            GFS weather data array
        """
        if isinstance(time, datetime.datetime):
            time = [time]

        channels = ERA5_CHANNELS if variables == "*" or "*" in variables else variables

        # Create cache dir if doesnt exist
        pathlib.Path(self.cache).mkdir(parents=True, exist_ok=True)

        # Make sure input time is valid
        self._validate_time(time)

        # Fetch index file for requested time
        data_arrays = []
        for t0 in time:
            data_array = await self.fetch_gfs_dataarray(t0, channels)
            data_arrays.append(data_array)

        # Delete cache if needed
        if not self._keep_cache:
            shutil.rmtree(self.cache)

        return xr.concat(data_arrays, dim="time")

    async def fetch_gfs_dataarray(
        self,
        time: datetime.datetime,
        channels: List[str],
    ) -> xr.DataArray:
        """Retrives GFS data array for given date time by fetching the index file,
        fetching variable grib files and lastly combining grib files into single data
        array.

        Parameters
        ----------
        time : datetime.datetime
            Date time to fetch
        channels : list[str]
            List of atmosphric variables to fetch. Must be supported in GFS lexicon

        Returns
        -------
        xr.DataArray
            GFS data array for given date time

        Raises
        ------
        KeyError
            Un supported variable.
        """
        logging.info("Fetching GFS index file: %s", time)
        index_file = self._fetch_index(time)

        file_name = f"gfs.{time.year}{time.month:0>2}{time.day:0>2}/{time.hour:0>2}"
        # Would need to update "f000" for getting forecast steps
        file_name = f"{file_name}/atmos/gfs.t{time.hour:0>2}z.pgrb2.0p25.f000"
        grib_file_name = f"{self._bucket_name}/{file_name}"

        gfsda = xr.DataArray(
            data=np.empty((1, len(channels), len(self.GFS_LAT), len(self.GFS_LON))),
            dims=["time", "channel", "lat", "lon"],
            coords={
                "time": [time],
                "channel": channels,
                "lat": self.GFS_LAT,
                "lon": self.GFS_LON,
            },
        )

        if self._concurrency == "async_proc_pool":
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor(
                self._num_processes, mp_context=mp.get_context("spawn")
            ) as pool:
                tasks = []
                for i, channel in enumerate(channels):
                    gfs_name, modifier = self.get_channel_data(channel)

                    if gfs_name not in index_file:
                        raise KeyError(
                            f"Could not find variable {gfs_name} in index file"
                        )

                    byte_offset = index_file[gfs_name][0]
                    byte_length = index_file[gfs_name][1]
                    # Download the grib file to cache
                    logging.info(
                        "asyncio pool executor: scheduling loading of data for channel %s",
                        channel,
                    )
                    tasks.append(
                        loop.run_in_executor(
                            pool,
                            call_download_s3_grib_cached,
                            self,
                            grib_file_name,
                            byte_offset,
                            byte_length,
                        )
                    )
                await asyncio.gather(*tasks)
                grib_files = [t.result() for t in tasks]
        elif self._concurrency == "dask":
            # downloading files in parallel
            delayed_files = []
            for i, channel in enumerate(channels):
                gfs_name, modifier = self.get_channel_data(channel)

                if gfs_name not in index_file:
                    raise KeyError(f"Could not find variable {gfs_name} in index file")

                byte_offset = index_file[gfs_name][0]
                byte_length = index_file[gfs_name][1]
                # Download the grib file to cache
                logging.info("Dask-scheduled loading of data for channel %s", channel)
                delayed_files.append(
                    dask.delayed(self.download_s3_grib_cached)(  # type: ignore
                        grib_file_name, byte_offset=byte_offset, byte_length=byte_length
                    )
                )
            r = dask.compute(delayed_files)
            if isinstance(r, tuple):
                grib_files = r[0]
            else:
                assert isinstance(r, list)
                grib_files = r
        elif self._concurrency == "none":
            grib_files = []
            for i, channel in enumerate(channels):
                gfs_name, modifier = self.get_channel_data(channel)

                if gfs_name not in index_file:
                    raise KeyError(f"Could not find variable {gfs_name} in index file")

                byte_offset = index_file[gfs_name][0]
                byte_length = index_file[gfs_name][1]
                logging.info("Non-concurrently loading data for channel %s", channel)
                grib_files.append(
                    self.download_s3_grib_cached(
                        grib_file_name, byte_offset=byte_offset, byte_length=byte_length
                    )
                )
        for i, channel in enumerate(channels):
            gfs_name, modifier = self.get_channel_data(channel)
            grib_file = grib_files[i]
            # Open into xarray data-array
            da = xr.open_dataarray(
                grib_file, engine="cfgrib", backend_kwargs={"indexpath": ""}
            )
            gfsda[0, i] = modifier(da.values)

        return gfsda

    def _validate_time(self, times: List[datetime.datetime]) -> None:
        """Verify if date time is valid for GFS

        Parameters
        ----------
        times : list[datetime.datetime]
            List of date times to fetch data
        """
        for time in times:
            if not time.hour % 6 == 0:
                raise ValueError(
                    f"Requested date time {time} needs to be 6 hour interval for GFS"
                )

            if time < datetime.datetime(year=2021, month=2, day=26):
                raise ValueError(
                    f"Requested date time {time} needs to be after Feburary 26th, 2021 for GFS"
                )

            if not self.available(self._bucket_name, time):
                raise ValueError(f"Requested date time {time} not available in GFS")

    def _fetch_index(self, time: datetime.datetime) -> Dict[str, Tuple[int, int]]:
        """Fetch GFS atmospheric index file

        Parameters
        ----------
        time : datetime.datetime
            Date time to fetch

        Returns
        -------
        dict[str, tuple[int, int]]
            Dictionary of GFS vairables (byte offset, byte length)
        """
        # https://www.nco.ncep.noaa.gov/pmb/products/gfs/
        file_name = f"gfs.{time.year}{time.month:0>2}{time.day:0>2}/{time.hour:0>2}"
        file_name = f"{file_name}/atmos/gfs.t{time.hour:0>2}z.pgrb2.0p25.f000.idx"
        s3_uri = f"{self._bucket_name}/{file_name}"
        # Grab index file
        index_file = self._download_s3_index_cached(s3_uri)
        with open(index_file, "r", encoding="utf-8") as file:
            index_lines = [line.rstrip() for line in file]

        index_table = {}
        # Note we actually drop the last variable here (Vertical Speed Shear)
        for i, line in enumerate(index_lines[:-1]):
            lsplit = line.split(":")
            if len(lsplit) < 7:
                continue

            nlsplit = index_lines[i + 1].split(":")
            byte_length = int(nlsplit[1]) - int(lsplit[1])
            byte_offset = int(lsplit[1])
            key = f"{lsplit[3]}::{lsplit[4]}"
            if byte_length > self.MAX_BYTE_SIZE:
                raise ValueError(
                    f"Byte length, {byte_length}, of variable {key} larger than safe threshold of {self.MAX_BYTE_SIZE}"
                )

            index_table[key] = (byte_offset, byte_length)

        # Pop place holder
        return index_table

    def _download_s3_index_cached(self, path: str) -> str:
        sha = hashlib.sha256(path.encode())
        filename = sha.hexdigest()

        cache_path = os.path.join(self.cache, filename)
        fs = s3fs.S3FileSystem(anon=True, client_kwargs={})
        fs.read_timeout = self.read_timeout
        fs.connect_timeout = self.connect_timeout
        fs.get_file(path, cache_path)

        return cache_path

    def download_s3_grib_cached(
        self, path: str, byte_offset: int, byte_length: int
    ) -> str:
        sha = hashlib.sha256((path + str(byte_offset)).encode())
        filename = sha.hexdigest()

        cache_path = os.path.join(self.cache, filename)
        logging.info("Opening S3 filesystem")
        fs = s3fs.S3FileSystem(anon=True, client_kwargs={})
        fs.read_timeout = self.read_timeout
        fs.connect_timeout = self.connect_timeout
        logging.info(f"Checking if {cache_path} exists")
        if not pathlib.Path(cache_path).is_file():
            logging.info(f"Reading {path} from offset {byte_offset}")
            data = fs.read_block(path, offset=byte_offset, length=byte_length)
            with open(cache_path, "wb") as file:
                logging.info(f"Writting to {cache_path}")
                file.write(data)

        return cache_path

    @property
    def cache(self) -> str:
        """Cache location"""
        cache_location = os.path.join(self._cache_folder, "gfs")
        if not self._keep_cache:
            cache_location = os.path.join(cache_location)
        return cache_location

    @classmethod
    def available(
        cls,
        bucket_name,
        time: datetime.datetime,
    ) -> bool:
        """Checks if given date time is avaliable in the GFS object store

        Parameters
        ----------
        time : datetime.datetime
            Date time to access

        Returns
        -------
        bool
            If date time is avaiable
        """
        s3 = boto3.client(
            "s3", config=botocore.config.Config(signature_version=UNSIGNED)  # type: ignore
        )
        # Object store directory for given time
        # Should contain two keys: atmos and wave
        file_name = f"gfs.{time.year}{time.month:0>2}{time.day:0>2}/{time.hour:0>2}/"
        try:
            resp = s3.list_objects_v2(
                Bucket=bucket_name, Prefix=file_name, Delimiter="/", MaxKeys=1
            )
        except botocore.exceptions.ClientError as e:  # type: ignore
            logging.error("Failed to access from GFS S3 bucket")
            raise e

        return "KeyCount" in resp and resp["KeyCount"] > 0

    @classmethod
    def get_channel_data(cls, val: str) -> Tuple[str, Callable]:
        """Return possibly modded channel data"""
        gfs_key = ERA5_TO_GFS_S3_MAP[val]
        if gfs_key.split("::")[0] == "HGT":

            def mod(x: np.array) -> np.array:  # type: ignore
                return x * 9.81

        else:

            def mod(x: np.array) -> np.array:  # type: ignore
                return x

        return gfs_key, mod


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        nargs="?",
        type=lambda s: datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S"),
        default=datetime.datetime(year=2023, month=1, day=1),
    )
    args = parser.parse_args()

    async def async_main():
        time_string = args.date.isoformat().replace("-", "_").replace(":", "_")
        the_da = await GFS(
            bucket_name="noaa-gfs-bdp-pds", cache_folder=".", verbose=True
        )(time=args.date, variables=["mrr"])
        the_da = the_da.astype(np.float32)  # Explicitly cast to fp32 to save space
        the_da.to_dataset(name="fields").to_netcdf(f"gfs_{time_string}.nc")

    asyncio.run(async_main())

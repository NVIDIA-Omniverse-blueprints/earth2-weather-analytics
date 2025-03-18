# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.

import base64
import io
import json
import os
from typing import Any, Dict, List
import numpy as np
from pydantic import JsonValue
import xarray
from PIL import Image

from dfm.api.dfm import TextureFile
from dfm.api.response._response_body import ResponseBody
from dfm.api.response._value_response import ValueResponse
from dfm.service.common.logging._logging import shorten
from dfm.service.common.request import DfmRequest
from dfm.service.common.exceptions import DataError
from dfm.service.common.xarray_schema import Dim
from dfm.service.common.xarray_schema import XarraySchema
from dfm.service.common.xarray_schema._var import Var
from dfm.service.execute.adapter import CachingIterator
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import Adapter, UnaryAdapter
from dfm.config.adapter.xarray import RenderUint8ToImages as RenderUInt8ToImagesConfig
from dfm.api.xarray import RenderUint8ToImages as RenderUInt8ToImagesParams


class RenderUint8ToImagesCachingIterator(CachingIterator):
    """
    A RenderUint8ToImagesCachingIterator is a caching iterator for the RenderUint8ToImages adapter.
    """

    async def write_value_to_cache(self, element_counter: int, item: Any):
        # the RenderUint8ToImages adapter calls explicit write in the body (for now),
        # so no need to write anything in the stream
        pass

    def write_file(self, filename: str, contents: bytes | JsonValue) -> str:
        path = f"{self.full_cache_folder_path}/{filename}"
        fs = self.filesystem
        as_bytes = (
            contents
            if isinstance(contents, bytes)
            else json.dumps(contents, indent=4).encode("utf-8")
        )
        fs.pipe(path, as_bytes)
        return path

    async def load_values_from_cache(
        self, _expected_num_elements: int
    ) -> List[Any] | None:
        fs = self.filesystem

        metadata_file = f"{self.full_cache_folder_path}/metadata.json"
        if fs.exists(metadata_file) and self.adapter.params.return_meta_data:
            metadata_url = metadata_file
            with fs.open(metadata_file, mode="r") as f:
                as_str = f.read()
                metadata = json.loads(as_str)
        else:
            metadata_url = None
            metadata = None

        results = []
        for url in fs.glob(
            f"{self.full_cache_folder_path}/*.{self.adapter.config.format}"
        ):
            basename = os.path.basename(url)  # type: ignore
            filename, extension = os.path.splitext(basename)
            if extension.startswith("."):
                extension = extension[1:]
            timestamp, _variable = filename.split("_", 1)
            # Filenames are like 2022-09-19T00C00_t2m, we want %Y-%m-%dT%H:%M
            timestamp = timestamp.replace("C", ":")

            if self.adapter.params.return_image_data:
                with fs.open(url) as f:
                    img_bytes = f.read()
                    img_str = base64.b64encode(img_bytes).decode()
            else:
                img_str = None

            result = TextureFile(
                metadata_url=metadata_url,
                url=url,
                format=self.adapter.config.format,
                timestamp=timestamp,
                metadata=metadata,
                base64_image_data=img_str,
            )
            results.append(result)

        return results


class RenderUint8ToImages(
    UnaryAdapter[Provider, RenderUInt8ToImagesConfig, RenderUInt8ToImagesParams],
    input_name="data",
):
    """
    A RenderUint8ToImages adapter is an adapter that renders a uint8 dataset to images.
    """

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: RenderUInt8ToImagesConfig,
        params: RenderUInt8ToImagesParams,
        data: Adapter,
    ):
        super().__init__(dfm_request, provider, config, params, data)

    def collect_local_hash_dict(self) -> Dict[str, Any]:
        return self._collect_local_hash_dict_helper(
            exclude_params=["return_image_data", "return_meta_data"],
            format=self.config.format,
            quality=self.config.quality,
        )

    def _instantiate_caching_iterator(self):
        cache_fsspec_conf = self.provider.cache_fsspec_conf()
        if cache_fsspec_conf:
            return RenderUint8ToImagesCachingIterator(
                self, cache_info=cache_fsspec_conf
            )
        return None

    def body(self, data: xarray.Dataset) -> Any:
        class TextureInputSchema(XarraySchema):
            pass

        TextureInputSchema.add_dynamic_attribute(
            self.params.xydims[0], Dim(np.floating, (0, None))
        )
        TextureInputSchema.add_dynamic_attribute(
            self.params.xydims[1], Dim(np.floating, (0, None))
        )
        TextureInputSchema.add_dynamic_attribute(
            self.params.time_dimension, Dim(np.dtype("datetime64"), (0, None))
        )
        for var in data.data_vars:
            TextureInputSchema.add_dynamic_attribute(
                var,
                Var(
                    np.dtype("uint8"),
                    self.params.time_dimension,
                    self.params.xydims[0],
                    self.params.xydims[1],
                    minmax=(0, 255),
                ),
            )

        TextureInputSchema.validate(data, allow_extras=True)

        # Find out which variable to render; either there is only one or we require the
        # user to pass the name
        if self.params.variable:
            if self.params.variable not in data:
                raise DataError(
                    f"Variable {self.params.variable} selected for rendering "
                    f"does not exist in dataset {data.dims}"
                )
            one_variable = data[self.params.variable]
        else:
            data_vars_names = [v for v in data.data_vars]
            if len(data_vars_names) != 1:
                raise DataError(
                    f"Data has multiple variables {data_vars_names}. "
                    "Need an explicit 'variable' parameter."
                )
            one_variable = data[data_vars_names[0]]

        # Compute the metadata
        # y dim is lat, x dim is lon
        lat_min = data[self.params.xydims[1]].min().item()
        lat_max = data[self.params.xydims[1]].max().item()
        lon_min = data[self.params.xydims[0]].min().item()
        lon_max = data[self.params.xydims[0]].max().item()

        # correct lon_max by one step size
        longitudes = data[self.params.xydims[0]]
        lon_step_size = (
            (longitudes[1] - longitudes[0]).item() if len(longitudes) > 1 else 0.0
        )
        lon_max += abs(lon_step_size)

        meta = (
            {  # write lon and lat info plus all the xarray attributes
                "lon_minmax": [lon_min, lon_max],
                "lat_minmax": [lat_min, lat_max],
            }
            | one_variable.attrs
            | (self.params.additional_meta_data or {})
        )

        if self._caching_iterator:
            metadata_url = (
                self._caching_iterator.write_file("metadata.json", meta)
                if self.caching_iterator
                else None
            )
        else:
            metadata_url = None

        metadata = meta if self.params.return_meta_data else None

        # now render each timestep (inside a coroutine)
        num_timesteps = data.sizes[self.params.time_dimension]

        async def async_body():
            for i in range(num_timesteps):
                one_timestep = one_variable.isel(
                    {self.params.time_dimension: i}, missing_dims="ignore"
                )
                np_arr = one_timestep.to_numpy().astype(np.uint8)
                # apparently it can sometimes happen that we get all-black textures;
                the_sum = np_arr.sum()
                if the_sum == 0 or the_sum == 1:
                    self._logger.error(
                        "Image was all %s, possibly bad normalization?: %s",
                        the_sum,
                        one_timestep,
                    )

                # create the image
                img_pil = Image.fromarray(np_arr.transpose())
                img_options = (
                    {"quality": self.config.quality} if self.config.quality else {}
                )
                with io.BytesIO() as bio:
                    img_pil.save(bio, format=self.config.format, **img_options)  # type: ignore
                    img_bytes = bio.getvalue()

                    # in case we want to send it back to the client
                    img_str = (
                        base64.b64encode(img_bytes).decode()
                        if self.params.return_image_data
                        else None
                    )

                    time_str = (
                        one_timestep[self.params.time_dimension]
                        .time.dt.strftime("%Y-%m-%dT%H:%M")
                        .item(0)
                    )

                    # if a cache is configured, write it
                    if self._caching_iterator:
                        filename = f"{time_str.replace(':', 'C')}_{one_timestep.name}.{self.config.format}"
                        file_url = self.caching_iterator.write_file(filename, img_bytes)
                    else:
                        file_url = None

                # create the result object and yield
                result = TextureFile(
                    metadata_url=metadata_url,
                    url=file_url,
                    format=self.config.format,
                    timestamp=time_str,
                    metadata=metadata,
                    base64_image_data=img_str,
                )
                self._logger.info("Returning result %s", shorten(result))
                yield result

        return async_body()

    async def prepare_to_send(
        self, result: TextureFile
    ) -> ResponseBody:  # pylint: disable=arguments-renamed
        return ValueResponse(value=result.model_dump())

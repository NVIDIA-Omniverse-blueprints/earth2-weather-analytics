# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.



from datetime import datetime
# Import DFM API and client packages that can be used to build and run pipelines.
from nv_dfm_core.api import Pipeline
from nv_dfm_core.api import StopToken, ErrorToken, Pipeline
from nv_dfm_core.session import Session, JobStatus, Job

#from federation.api import TextureFile, GeoJsonFile, TextureFileList

class PipelineBase:

    @property
    def name(self) -> str:
        pass

    def _create_pipeline(
        variables: list[str], date: datetime, **kwargs
    ) -> Pipeline:
        """
        A helper function that uses provided settings to build a pipeline.
        """
        pass

    @classmethod
    def pipeline_callback(cls, response) -> None:
        """Pipeline call back after successful response

        Parameters
        ----------
        response :
            DFM Response object
        """
        pass

    @classmethod
    def input_validation(cls, variables: list[str], dateobj: datetime) -> None:
        """Offline check input requests

        Check the DFM code, for look for advice decorators,

        Parameters
        ----------
        variables : list[str]
            List of variables to fetch
        dateobj : str
            Date time object to fetch

        Raises
        ------
        ValueError
            If invalid inputs
        """
        pass

    @classmethod
    def execute(cls, variable: str, date: str):
        """Sync execute script for DFM pipelines

        Parameters
        ----------
        variables : str
            Variable to fetch
        date : str
            ISO formated datetime string

        Returns
        -------
        Future[Any]
            future of the running coroutine the pipeline is executed in
        """
        pass

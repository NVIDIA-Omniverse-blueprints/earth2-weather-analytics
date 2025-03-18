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
from dfm.api import Process
from dfm.api.response import ValueResponse

class PipelineBase:

    @property
    def name(self) -> str:
        pass

    def _create_pipeline(
        variables: list[str], date: datetime, **kwargs
    ) -> Process:
        """
        A helper function that uses provided settings to build a pipeline.
        """
        pass

    @classmethod
    def pipeline_callback(cls, response: ValueResponse) -> None:
        """Pipeline call back after successful response

        Parameters
        ----------
        response : ValueResponse
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
    def execute(cls, variable: str, date: str, dfm_url: str = "http://localhost:8080"):
        """Sync execute script for GFS pipeline

        Parameters
        ----------
        variables : str
            Variable to fetch
        date : str
            ISO formated datetime string
        dfm_url : str, optional
            URL of running DFM server, by default "http://localhost:8080"

        Returns
        -------
        Future[Any]
            future of the running coroutine the pipeline is executed in
        """
        pass

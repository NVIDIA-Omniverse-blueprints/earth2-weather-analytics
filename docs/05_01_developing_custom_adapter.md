# Developing a Custom DFM Adapter

Just to reiterate from the [general description](./05_data_federation_mesh.md#developing-a-custom-adapter), developing a new adapter requires the following three components:
* Creating the pipeline for DFM to execute - Refer to the reference ([source code here](https://github.com/NVIDIA-Omniverse-blueprints/earth2-weather-analytics/tree/main/src/dfm/service/execute/adapter/esri))
* Defining the corresponding API Spec in the ([API folder](https://github.com/NVIDIA-Omniverse-blueprints/earth2-weather-analytics/tree/main/src/dfm/api/esri))
* Specifying the relevant configuration in the ([Config folder](https://github.com/NVIDIA-Omniverse-blueprints/earth2-weather-analytics/tree/main/src/dfm/config/adapter/esri))

Please refer to the sequence diagram for ([understanding the control flow](https://github.com/NVIDIA-Omniverse-blueprints/earth2-weather-analytics/blob/ram-cherukuri-patch-1/docs/06_sequence.md))

## Development Setup

### Dependency Management

[Poetry](https://python-poetry.org/) is used to manage DFM Python dependencies.

DFM client library and services dependencies are separated into different Poetry groups: 
* `main` - default Poetry group; contains default dependencies for DFM Client,
* `core` - adds dependencies required by DFM services,
* `dev` - contains dependencies for development and testing (such as `pytest`).

See [Poetry documentation](https://python-poetry.org/docs/managing-dependencies/#layering-optional-groups)
to learn more about groups and how to use them.

To set up your DFM development environment, follow the steps below.

### Setting Up Development Environment

**Note:** This setup has been tested on Ubuntu 22.04 with Python 3.12. 
It may require additional steps and installations to use it on another OS or with a newer Python version.

**Step 1**: Install base dependencies:

```
sudo apt update && sudo apt install -y curl gcc
```

**Step 2**: Install `conda` and `poetry`. 
If you already have `conda` and `poetry` installed, proceed to **Step 3**.
Use of `conda` is not mandatory, you can use any other tool for environment management.

Installing `conda` using Miniforge distribution is described in [Miniforge documentation](https://conda-forge.org/download/).

It is recommended to install `poetry` outside of python virtual environment that is used for the development to prevent its dependencies from being overwritten. 

This setup uses `pipx` to install Poetry:
```bash
pip install pipx
pipx install poetry
pipx ensurepath
```

**Step 3**: Create `conda` environment:

```bash
conda create -y -n dfm python=3.12
conda activate dfm
```

### Installing Dependencies

This will install all core and development dependencies:
```bash
cd src/
poetry install --with core,dev
```

If you need to add a new dependency to the project, run:
```bash
poetry add --group <group> ...
```
Pay attention when choosing the group to add the dependency to (see [above](#dependency-management)).

## Testing

To run the tests, make sure you used `dev` group during installation.

Run DFM tests:

```bash
# Make sure you're in the src/ directory!
pytest tests/
```

## Defining API

With development environment ready and tested, we can start developing a new adapter. Let's develop an adapter for ingesting
[Global Deterministic Prediction System (GDPS)](https://eccc-msc.github.io/open-data/msc-data/nwp_gdps/readme_gdps-datamart_en/#data-location)
data. 

To start with, we will obtain 2-meter temperature data from date and time provided by the adapter parameter.
Here is how the adapter API could look like:

```python
"""DfmFunction to load GDPS Data"""

from typing import Literal, Dict, List, Optional

from .. import FunctionCall


class LoadGdpsModelData(FunctionCall, frozen=True):
    """
    Function to load GDPS data. 
    
    Args:
        time: starting time of GDPS forecast
                   the source provides.
        
    Function Returns:
        xarray.Dataset with the specified variables and selection.
    
    Client Returns:
        -
    """

    api_class: Literal["dfm.api.data_loader.LoadGdpsModelData"] = (
        "dfm.api.data_loader.LoadGdpsModelData"
    )
    time : str
```

Save this file to `_load_gdps_model_data.py` file in [DFM API models directory](../src/dfm/api/data_loader/).

**Important** Add a relevant import clause to [API module init file](../src/dfm/api/data_loader/__init__.py).

## Creating configuration model

An adapter can be configured by the site administrator to reflect local requirements. Let's create a configuration
model for our GDPS loader in `_load_gdps_data.py` file in [DFM configuration models directory](../src/dfm/config/adapter/data_loader/):

```python
"""Loader for GDPS data configuration"""

from typing import Literal
from .._adapter_config import AdapterConfig


class LoadGdpsData(AdapterConfig, frozen=True):
    """Config for LoadGdpsData Adapter"""

    adapter_class: Literal["adapter.data_loader.LoadGdpsData"] = (
        "adapter.data_loader.LoadGdpsData"
    )
    model: str = "gdps"
    variable: str = "TMP"
    level: str = "TGL_2"
    fxx: int = 0
```
Remember to add relevant import clause to [config module init file](../src/dfm/config/adapter/data_loader/__init__.py).

## Adapter implementation

We have two important building blocks in place (API and configuration), it's time to implement the adapter. 
We can conviniently use [Herbie data loader](https://herbie.readthedocs.io/en/stable/gallery/eccc_models/gdps.html) to help us with downloading and parsing the data. Herbie loader can return data in `xarray` format,
which is the common format used by DFM adapters to exchange data. We only need to do some minor processing
to match xarray schema required by other DFM adapters (such as texture creation adapter).

Save the following adapter code to `_load_gdps_data.py` file in [DFM Execute service directory](../src/dfm/service/execute/adapter/data_loader/).

```python
import dateutil.parser

from typing import Any

from herbie import Herbie

from dfm.service.common.request import DfmRequest
from dfm.service.execute.provider import Provider
from dfm.service.execute.adapter import NullaryAdapter
from dfm.api.data_loader import LoadGdpsModelData as LoadGdpsModelDataParams
from dfm.config.adapter.data_loader import LoadGdpsData as LoadGdpsDataConfig

class LoadGdpsData(
    NullaryAdapter[Provider, LoadGdpsDataConfig, LoadGdpsModelDataParams]
):
    """
    Adapter to load GDPS data from ECCC.

    This adapter provides functionality to load GDPS data based on user-specified parameters.

    The adapter supports the following parameters:
    - time: The start time of the data to load

    The adapter will load the data for the specified time and return a dataset
    containing the requested variables.
    """

    DATE_FORMAT = "%Y-%m-%dT%H:00"

    def __init__(  # pylint: disable=useless-parent-delegation
        self,
        dfm_request: DfmRequest,
        provider: Provider,
        config: LoadGdpsDataConfig,
        params: LoadGdpsModelDataParams,
    ):
        super().__init__(dfm_request, provider, config, params)

    def body(self) -> Any:
        # Parse the time parameter
        try:
            time = dateutil.parser.parse(self.params.time)
        except dateutil.parser.ParserError:
            raise ValueError(f"Invalid start time {self.params.time}.")

        self._logger.info("Loading GDPS data for time: %s", time)

        H = Herbie(
            time,
            model="gdps",
            fxx=0,
            variable="TMP",
            level="TGL_2",
        )

        ds = H.xarray()

        # Add time dimension to dataset
        ds = ds.expand_dims(dim={
            "time": [time]
        })
        ds = ds.drop_vars([
            "step",
            "heightAboveGround",
            "valid_time",
            "gribfile_projection"
        ])
        # Flip latitude dimension from -90:90 to 90:-90
        ds = ds.reindex(latitude=ds.latitude[::-1])

        self._logger.info("GDPS data loaded successfully")

        return ds
```

Remember about adding necessary import line to module's init file!

## Unit Testing

Let's create a basic unit test for our adapter, providing a mock execution environment. 
Save the following code in `test_dfm_service_execute_adapter_load_gdps_data.py` file in
[DFM tests directory](../src/tests/dfm/).


```python
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import xarray

from dfm.api import FunctionCall
from dfm.api.data_loader import LoadGdpsModelData as LoadGdpsModelDataParams
from dfm.config.adapter.data_loader import LoadGdpsData as LoadGdpsDataConfig
from dfm.service.execute.adapter.data_loader import LoadGdpsData

from tests.common import MockDfmRequest

pytest_plugins = ("pytest_asyncio",)


def create_adapter(params: LoadGdpsModelDataParams):
    class TestProvider:
        provider = "testprovider"

        def cache_fsspec_conf(self):
            return None

    config = LoadGdpsDataConfig()
    adapter = LoadGdpsData(
        MockDfmRequest(this_site="here"),
        TestProvider(),  # provider # type: ignore
        config,
        params,
    )
    return adapter


async def run_gdps_adapter(time: str = "2025-05-12T00:00"):
    FunctionCall.set_allow_outside_block()
    params = LoadGdpsModelDataParams(time=time)
    FunctionCall.unset_allow_outside_block()
    adapter = create_adapter(params)
    result = []
    async for r in await adapter.get_or_create_stream():
        result.append(r)

    assert len(result) == 1
    assert all(isinstance(r, xarray.Dataset) for r in result)

    return result[0] if len(result) == 1 else result


@pytest.mark.asyncio
async def test_coordinates():
    """Test that coordinates has expected shapes and values."""
    recent = pd.Timestamp("now").floor("12h") - pd.Timedelta("12h")
    ds = await run_gdps_adapter(time=recent.strftime("%Y-%m-%dT%H:%M"))

    assert "time" in ds
    assert "longitude" in ds
    assert "latitude" in ds

    assert ds["time"] == np.datetime64(recent)

```

To run it, simply use `pytest`:
```bash
pytest -sv src/tests/dfm/test_dfm_service_execute_adapter_load_gdps_data.py
```

**Note** On some systems, there might be a conflict of available EC Codes libraries
versions. It usually leads to crashes or errors in code execution.
You can force Python modules to use the version provided
by the operating system by setting the following environmental variables:

```bash
export ECCODES_PYTHON_USE_FINDLIBS=1
export LD_LIBRARY_PATH=/lib/x86_64-linux-gnu/
```

Please adjust the `LD_LIBRARY_PATH` value depending on your operating system.

## Deployment to microk8s

Let's add our adapter to the local `microk8s` cluster. 

**Step 1: Update configuration**

To configure the GDPS adapter in the local DFM deployment, go to 
[site configuration file](../deploy/helm/templates/site-config.yaml) file and modify
the `dfm` provider configuration by adding mapping from API to Execute adapter class.
The section should look similarly to this:

```yaml
dfm:
    provider_class: provider.BasicProvider
    description: The default provider for most operations
    interface:
        dfm.api.dfm.Constant: dfm.service.execute.adapter.dfm.Constant
        dfm.api.dfm.Execute: dfm.service.execute.adapter.dfm.Execute
        dfm.api.dfm.SignalClient: dfm.service.execute.adapter.dfm.SignalClient
        dfm.api.dfm.SignalAllDone: dfm.service.execute.adapter.dfm.SignalAllDone
        dfm.api.dfm.PushResponse: dfm.service.execute.adapter.dfm.PushResponse
        dfm.api.xarray.AveragePointwise: dfm.service.execute.adapter.xarray.AveragePointwise
        dfm.api.xarray.ConvertToUint8: dfm.service.execute.adapter.xarray.ConvertToUint8
        dfm.api.xarray.VariableNorm: dfm.service.execute.adapter.xarray.VariableNorm
        # Add GDPS adapter configuration
        dfm.api.data_loader.LoadGdpsModelData: dfm.service.execute.adapter.data_loader.LoadGdpsData
```

Rebuild the images and redeploy DFM:
```bash
deploy/deploy_microk8s.sh -w -n -f
```

## End to End Pipeline

Now we can create an end-to-end test and a DFM pipeline that will use the GDPS adapter to
download temperature data and create a grayscale texture that could be used to visualize
data in Earth-2 Command Center. Save the following code (mostly the same as, for example
[HRRR pipeline](../src/pipelines/hrrr.py)) to `gdps.py` file in [pipelines directory](../src/pipelines/):

```python
"""
This example demonstrates how to build an execution pipeline for the Earth2 Blueprint,
and use the client library to run the pipeline. It also shows how to handle received responses.
"""

# Import basic Python packages.
import argparse
import asyncio
import base64
import logging

from enum import Enum, auto
from pathlib import Path
import pandas as pd

from dfm.api import Process, well_known_id
from dfm.api.dfm import SignalClient
from dfm.api.data_loader import LoadGdpsModelData
from dfm.api.xarray import ConvertToUint8, RenderUint8ToImages
from dfm.api.response import ValueResponse, StatusResponse, HeartbeatResponse

from dfm.client import AsyncClient

# Configure simple logging facility
logging.basicConfig(level=logging.INFO)


class PipelineVariant(Enum):
    """
    This example provides multiple pipelines that can be built and executed.
    """

    EARTH2_GDPS = auto()


class PipelineFactory:
    """
    A convenience class that helps building Pipeline objects
    that can be submitted to the DFM for execution.
    """

    @classmethod
    def get(cls, variant: str | PipelineVariant):
        """
        Translates pipeline variant to actual pipeline object
        using factory functions.
        """
        if isinstance(variant, str):
            variant = PipelineVariant[variant.upper()]
        return getattr(PipelineFactory, variant.name.lower())()

    def earth2_gdps():
        """
        Returns GDPS pipeline.
        """
        force_loader_compute = True  # Disable loader cache.
        force_texture_compute = True  # Disable texture cache.

        xydims = ('longitude', 'latitude')

        recent = pd.Timestamp("now").floor("24h")
        time=recent.strftime("%Y-%m-%dT%H:%M")

        with Process() as pipeline:
            data = LoadGdpsModelData(
                time=time,
                force_compute=force_loader_compute
            )
            
            tex = ConvertToUint8(
                data=data,
                time_dimension='time',
                xydims=xydims,
                force_compute=force_texture_compute
            )
            
            render_images = RenderUint8ToImages(
                provider='local_earth2_textures',
                node_id=well_known_id('image'),
                is_output=True,
                data=tex,
                time_dimension='time',
                xydims=xydims,
                force_compute=force_texture_compute,
                return_meta_data=True,
                return_image_data=True
            )
            # Send 'all_done' signal to the client when the processing is done.
            SignalClient(
                node_id=well_known_id("all_done"), after=render_images, message="done"
            )
        # Return the pipeline object.
        return pipeline


async def main(
    log: logging.Logger,
    dfm_url: str,
    pipeline_variant: str | PipelineVariant,
    verbose: bool = False,
):
    """
    This function demonstrates how to run a pipeline and process received responses.
    """
    # PipelineFactory returns a Python object describing the processing pipeline.
    pipeline = PipelineFactory.get(pipeline_variant)

    # We're using an asynchronous client for communication with the node
    async with AsyncClient(
        url=dfm_url, logger=logging.getLogger("earth2.client"), retries=5
    ) as client:
        # Obtain basic version information first to check connectivity.
        version = await client.version()
        log.info("Using DFM %s site %s", version, dfm_url)
        # Submit our pipeline for execution
        request_id = await client.process(pipeline)
        log.info("DFM accepted request and returned request ID %s", request_id)
        # Client returns an empty value, there's no response available,
        # but we should keep polling until
        #   a) timeout happens
        #   b) a new response is available
        # We tell the client to finish the loop when 'all_done' signal is received.
        async for response in client.responses(
            request_id=request_id,
            stop_node_ids=well_known_id("all_done"),
            return_statuses=True,
        ):
            if not response:
                # No responses available, back off a little
                await asyncio.sleep(0.5)
                continue
            # Raise an exception if we receive error response
            client.raise_on_error(response)
            # Now we know that the response is not indicating an error, so we need to check
            # what exactly we have received. We asked the client to return all responses,
            # including status updates and heart beats.
            if isinstance(response.body, ValueResponse):
                # We received a value.
                if response.node_id == well_known_id("image"):
                    # It's an image, so we get image data and save it to a file.
                    file_path = Path(response.body.value["url"]).name
                    image_data = base64.b64decode(
                        response.body.value["base64_image_data"]
                    )
                    with open(file_path, "wb") as file:
                        file.write(image_data)
                    log.info("Received image saved to %s", file_path)
                else:
                    # Not an image - just display the received value.
                    log.info("Received response: %s", response.body.value)
            elif isinstance(response.body, StatusResponse) and verbose:
                log.info("Received status update: %s", response.body.message)
            elif isinstance(response.body, HeartbeatResponse) and verbose:
                log.info("Received heartbeat")
        # Client received 'all_done' signal and finished iterating.
        log.info("Done.")


if __name__ == "__main__":
    log = logging.getLogger("earth2")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--site",
        default="http://localhost:8080",
        type=str,
        nargs="?",
        help="DFM site URL, defaults to local port-forwarded service",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Be more verbose: show status messages",
    )
    parser.add_argument(
        "-p",
        "--pipeline",
        default="earth2_gdps",
        type=str,
        nargs="?",
        help="Pipeline to execute",
    )
    args = parser.parse_args()

    try:
        pipeline_variant = PipelineVariant[args.pipeline.upper()]
    except KeyError:
        log.error("Unknown pipeline variant: %s", args.pipeline)
    else:
        asyncio.run(main(log, args.site, pipeline_variant, args.verbose))

```

You can now go ahead and run it:
```bash
python3 pipelines/gdps.py
```

If the program completes successfully, you should see a new JPEG file in your current working
directory, similar to this:
![Blueprint](./imgs/gdps-sample-image.jpeg)

<!-- Footer Navigation -->
---
<div align="center">

| Previous | Next |
|:---------:|:-----:|
| [Data Federation Mesh](./05_data_federation_mesh.md) | [Sequence Diagram](./06_sequence.md) |

</div>

# Data Federation Mesh (DFM)

The NVIDIA Earth-2 Weather Analytics Blueprint uses [Data Federation Mesh
(DFM)](https://github.com/NVIDIA/data-federation-mesh) to orchestrate pipelines
that load, process, and transform weather data for the E2CC Kit application and
Jupyter notebook workflows. This section summarizes key DFM concepts and how
they apply to the blueprint. For full details, refer to the [DFM User
Guide](https://nvidia.github.io/data-federation-mesh/userguide/index.html) and
related documentation.

## Overview

*Data Federation Mesh* (*DFM*) is a programmable framework for managing and
orchestrating data processing across distributed *sites*. It delivers "glue code
as a service". It coordinates where work runs and how data flows. A primary goal
is to bring compute to the data by running pipeline steps close to where data
lives. This reduces latency, bandwidth, and cost, and keeps data within desired
security boundaries. DFM is built on [NVIDIA Flare](https://developer.nvidia.com/flare),
which provides distributed messaging, job management, security, and deployment.
Multiple sites communicating in a peer-to-peer way form a *federation* and
expose a single, coherent *operations API* so clients can submit pipelines
without knowing the underlying topology.

### Federation and Sites

A **federation** is a closed, independent set of heterogeneous resources (data
sources, compute, and services) spread across multiple sites that collaboratively
implement common functionality. It has its own configuration, code, and
certificates.

A **site** is a group of services and resources deployed together in one
location, maintained by a **site administrator**. In a typical DFM deployment:

- **Homesite**: Accepts connections from DFM clients, manages requests, and
  holds results for clients to poll. In this blueprint, the notebook or E2CC
  acts as a client that connects to a homesite.
- **Controller site** (Flare server): Submits pipelines for execution and
  distributes jobs across computation sites.
- **Worker sites** (Flare workers): Host *adapters* and perform the actual
  computation.

The site administrator is responsible for configuring the site, deploying
services, and controlling the operations API that is exposed to users.

### Operations, Adapters, and Bindings

DFM exposes functionality to clients through an **operations API**. Users never
call adapters directly. Instead, they build pipelines from **operations**,
which define the signature (name, typed parameters, return types) and semantics
of a function. **Adapters** are plugin-like components that implement those
operations. They are bound to operations per site in the federation
configuration. **Bindings** define how each adapter is associated with an
operation at a site. They map adapter parameters to operation parameters,
constants, or secrets.

All of this is defined in the federation's YAML configuration (`.dfm.yaml`),
which lists operations, sites, and per-site interfaces that map operations to
adapter classes and their arguments. The DFM tooling generates API code from
this configuration so that clients can construct type-checked pipelines.

### Pipelines and Execution

Clients submit **pipelines**, which are JSON-serialized graphs whose nodes are
operations and whose edges represent data flow. Pipelines can run at two targets:

- **`local`**: Execution on a single machine using multiprocessing. No
  deployed federation is required. Useful for development and testing.
- **`flare`**: Execution within a DFM deployment over NVIDIA Flare (for example, POC
  mode or a full multi-site federation).

For distributed execution, pipelines are translated into Petrinet-like format
and run across the federation. The controller assigns work to worker sites, and
the homesite returns results to the client.

### The Client's View in This Blueprint

In this blueprint, the federation's operations are generated into the
`federation.fed.api` package. Clients (such as the example notebook or E2CC) import
operation types from that package and build pipelines by instantiating
operations and wiring outputs of one operation as inputs to another. For example:

```python
from federation.fed.api import dataloader, xarray

weather_data = dataloader.LoadGfsEra5Data(
    variables=...,
    ...
)
tex = xarray.ConvertToUint8(
    data=weather_data,
    ...
)
```

The pipeline is then submitted to the federation through a DFM session connected to
the homesite. The actual work is performed by the adapters bound to
those operations on the chosen sites. Adapter libraries such as
[nv-dfm-lib-weather](https://github.com/NVIDIA/data-federation-mesh/tree/main/packages/nv-dfm-lib-weather)
define both the operation schemas and the adapter implementations. This
blueprint's federation wires those into a single federation and does not
implement adapters in this repository unless you add custom ones.

For more on DFM concepts, configuration, and tutorials, refer to the
[DFM documentation](https://nvidia.github.io/data-federation-mesh/index.html).

## Developer Guide

The blueprint provides an example of a federation. The `earth-2-federation`
directory contains all the files needed for its configuration. This section
gives an overview of the key components and outlines how to add a new adapter.

### Key Components in the Earth-2 Federation

The following structure is under `earth-2-federation/`:

- **`federations.yaml`**: Registry for the federation. It points the DFM CLI to
  the federation config and project files.
- **`federation/configs/`**: Configuration that defines the federation:
  - **`federation.dfm.yaml`**: Core DFM federation definition. It declares the
    **operations** offered by the federation and, per **site**, the
    **interface** that defines which operations that site can execute, and how
    operations map to its adapter implementations.
  - **`project.yaml`**: Project and participant settings.
- **`federation/fed/`**: Generated by `dfm fed gen code earth2`. Do not edit
  these files by hand.
  - **`fed/api/`**: Operation types (such as `LoadGfsEra5Data`, `ConvertToUint8`)
    used by clients to build pipelines.
  - **`fed/site/<sitename>/`**: Per-site bindings that attach API operations to
    a site so the DFM knows where to run them.
  - **`fed/runtime/`**: **`fed_info.json`** (sites, interface, costs) and
    **`homesite/_this_site.py`** (homesite definition).
- **Two wheel packages**: Built from the same repo:
  - **`earth2_blueprint`** (full runtime): Used by the DFM site container.
    Includes the federation package and heavy dependencies (such as Earth2Studio).
    Built with `scripts/build-wheel.sh`.
  - **`earth2_blueprint_api`**: API-only package for clients that only need
    federation types and a thin client (such as notebooks and E2CC). Contains
    `federation.fed.api` with minimal dependencies. Built by
    `scripts/build-api-wheel.sh`, which copies the generated `federation/fed/`
    from the main build into the API package.

In this blueprint, operations and interfaces are referenced from the
[`nv-dfm-lib-weather`](https://github.com/NVIDIA/data-federation-mesh/tree/main/packages/nv-dfm-lib-weather)
package. This example federation does not implement its own adapters. However,
custom behavior can be added by defining new operations and adapters and wiring
them into the federation.

### Adding a New Adapter (High-Level Steps)

Use the steps below as a roadmap when adding a new operation or adapter to the
Earth-2 federation.

It is **highly recommended** to complete the DFM [Zero to Thirty
tutorial](https://nvidia.github.io/data-federation-mesh/tutorials-zero-to-thirty/00-introduction.html)
first. That walkthrough covers setting up a federation, and running it locally
and using the Flare POC mode. Doing so will make the steps below much easier
to follow.

1. **Implement the adapter**  
   Implement the code that the worker site invokes when the operation runs.
   For an example, see the implementation of the
   [SfnoPrognostic adapter](https://github.com/NVIDIA/data-federation-mesh/blob/main/packages/nv-dfm-lib-weather/nv_dfm_lib_weather/sfno/_sfno.py).

2. **Define operation and interface configs**  
   Add a **new YAML file** for your operation and corresponding interface under
   a config directory in this repo (for example, under `federation/configs/`),
   following the same structure as the
   [configs](https://github.com/NVIDIA/data-federation-mesh/tree/main/packages/nv-dfm-lib-weather/nv_dfm_lib_weather/configs)
   in the `nv-dfm-lib-weather` package.

3. **Update the federation config**  
   In **`federation/configs/federation.dfm.yaml`**:
   - Under **`operations`**, add a `$ref` (or merge in) the YAML that defines
     your operation.
   - Under the **target site's `interface`** (e.g. `sites.client1.interface`),
     add a `$ref` to the **interface** part of the config.

   This makes the operation part of the federation and exposes it on that site.

4. **Regenerate federation code**  
   From the **`earth-2-federation`** directory, run:

   ```bash
   uv run dfm fed gen code --cleanup earth2
   ```

   This regenerates **`federation/fed/`** (API types and site bindings) from the
   current `federation.dfm.yaml` and related configs.

5. **Rebuild the packages**  
   - Run **`scripts/build-wheel.sh`** to build updated versions of the two
     wheel packages.

6. **Use the new operation in pipelines**  
   After installing the updated wheels, clients can import the new operation
   types from `federation.fed.api` (or the appropriate submodule) and use
   them in pipelines.

<!-- Footer Navigation -->
---
<div align="center">

| Previous | Next |
|:---------:|:-----:|
| [Earth-2 Command Center](./02_omniverse_app.md) | [README](../README.md) |

</div>

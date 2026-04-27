# Earth-2 Blueprint Federation

A sample **DFM federation** for the Earth-2 Weather Analytics Blueprint. It composes adapters and operations from NVIDIA DFM libraries (e.g. `nv_dfm_lib_weather`) and lets you run data pipelines across sites without defining adapters in this repository. Custom adapters can be added here when needed.

## What this project is

- **Federation only** – Defines sites, operations, and interfaces by referencing configs from DFM libraries. It does not ship its own adapters; it wires existing ones into a single federation.
- **Pipelines** – You build data gathering and processing pipelines (e.g. load GFS/ERA5 → convert → render) that run on federated sites.
- **Extensible** – If you need new adapters or site logic, they can live in this repository; the federation config can then reference them or keep using library-provided ones.

## Two wheel packages

Two wheels are built:

| Package | Use case | Python | Dependencies |
|--------|----------|--------|--------------|
| **earth2-blueprint** | Full runtime: run the federation, example app, and pipelines. | 3.12+ | `nv_dfm_core` plus optional **federation** extra (`nv_dfm_lib_weather`, `nv_dfm_lib_common`, `earth2studio[data]`, etc.). |
| **earth2-blueprint-api** | API-only: types and client API for integrating with the federation (e.g. from another service). Minimal footprint. | 3.10+ | `nv_dfm_core`, `nv_dfm_lib_common` only. |

Use the **runtime** package when you need to run the POC or execute pipelines. Use the **API** package when you only need to depend on federation types and a thin client (e.g. Python 3.10 environments or services that talk to the federation without running it).

## Federation configuration

The federation is defined in the package at **`federation/configs/federation.dfm.yaml`**.

Flare project settings (participants, ports, etc.) are in **`federation/configs/project.yaml`** in the same directory.

## Prerequisites

- **Runtime:** Python 3.12+. **API:** Python 3.10+.
- Data Federation Manager (DFM) and the `dfm` CLI come from `nv_dfm_core` (a dependency of both packages).

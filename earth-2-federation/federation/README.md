# Earth-2 Blueprint Federation

This package is the **federation** component of the Earth-2 Blueprint. It is distributed as a wheel (`earth2-blueprint`) and provides the DFM federation definition, API types, and example app used to run data pipelines.

## Contents

- **`federation/configs/`** – Federation and project configuration:
  - **`federation.dfm.yaml`** – DFM federation (sites, operations, interfaces). Operations and site interfaces are composed from DFM libraries (e.g. `nv_dfm_lib_weather`); this repo does not define its own adapters unless added later.
  - **`project.yaml`** – Project/participant and port settings for the federation.
- **`federation/api/`** – Public API types (e.g. `TextureFile`, `TextureFileList`, `GeoJsonFile`) re-exported for apps and clients.

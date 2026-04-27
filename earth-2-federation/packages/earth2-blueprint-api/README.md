# earth2-blueprint-api

API-only package for integrating with the Earth-2 Blueprint federation **without** any dependency on the weather stack (nv_dfm_lib_weather, earth2studio, torch, CUDA, etc.).

## Contents

- **`federation.fed.api`** — DFM operation types (e.g. `LoadGfsEra5Data`, `ConvertToUint8`, `RenderUint8ToImages`) for use in pipelines. Depends only on `nv_dfm_core`.

This package does **not** include `federation.api` (TextureFile, TextureFileList, GeoJsonFile). For those, use the full `earth2-blueprint` package or `nv_dfm_lib_common` directly.

## Use case

Install this package when you want to:

- Write an app that connects to a running federation POC (e.g. `get_session(target="flare", ...)`).
- Use federation operation types (`federation.fed.api`) with a single dependency: `nv_dfm_core`.

## Dependencies

- **`nv_dfm_core`** only — DFM session and core types. No weather or ML dependencies.

Version is kept in sync with the full `earth2-blueprint` package.

## Updating this package

The `federation/` tree under this package is checked in. When the main repo’s `federation/fed/api` is regenerated (e.g. by DFM-APIGEN), copy the updated files:

- `federation/fed/__init__.py` → `packages/earth2-blueprint-api/federation/fed/`
- `federation/fed/api/*.py` → `packages/earth2-blueprint-api/federation/fed/api/`

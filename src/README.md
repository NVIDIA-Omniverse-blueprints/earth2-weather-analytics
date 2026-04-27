# DFM Site Container

This directory provides the **container that runs the DFM site** for the Earth-2
Weather Analytics Blueprint. The site receives pipelines from the Jupyter
notebook or Earth-2 Command Center (E2CC), executes them, and returns results.

## Prerequisites

The Earth-2 federation wheels must be built first. From the repository root,
run `./setup.sh` (see [Quickstart](../docs/01_quickstart.md)).

## Run the DFM site

From the **repository root**:

```bash
./src/run_container.sh
```

This builds the image (using `earth-2-federation/dist` for the federation
wheel), runs the container, and starts the DFM POC site. The container  mounts
`workspace/` so the notebook or E2CC can connect to the site.

To use the notebook or E2CC, start this container first, then run your client as
described in the [Quickstart](../docs/01_quickstart.md).

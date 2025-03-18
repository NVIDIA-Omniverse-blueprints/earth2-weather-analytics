# Earth-2 Weather Analytics Blueprint - Workflow Overview

Learn about the Earth-2 Weather Analytics Blueprint desktop and streaming workflows.

> [!IMPORTANT]
> For full reproducibility, this blueprint requires an [NVIDIA AI Enterprise](https://www.nvidia.com/en-us/ai/)
> license, but most parts can be deployed without one.
> You should adjust your deployment accordingly.
> An NVIDIA AI Enterprise license is required for the following features:
>
> - FourCastNet NIM
> - Omniverse Streaming Container

## Desktop Workflow

The desktop workflow serves as the primary deployment method for this blueprint.
In this workflow, both the data federation service and FourCastNet NIM are deployed
using Kubernetes to fetch weather data from different data stores and generate
AI-powered weather forecasts.

The desktop environment features an *Omniverse Kit* application bundled with
*Earth-2 Command Center* extensions, providing users with an interactive globe
interface for weather analytics and visualization.

When you interact with the Omniverse Kit application, it communicates your requests
to the running data federation service.
Upon receiving a request, the service executes the corresponding data pipeline and saves
the resulting textures to a shared cache location.
This shared cache enables seamless communication between the data federation service and
the Omniverse Kit application.
The Omniverse Kit application can then access these cached textures and render them
directly onto the interactive globe, creating a fluid visualization experience.

<div align="center">
<div align="center" style="max-width: 575px;">

![Desktop Workflow](./imgs/desktop_workflow.png)

</div>
</div>

## Streaming Workflow

The key difference between the desktop and streaming workflows is that the streaming
variant deploys the Omniverse application as a containerized service with a webRTC
streaming API.

This webRTC stream can then be integrated with a web application to allow for a fully
remote experience.

<div align="center">
<div style="max-width: 700px;">

![Streaming Workflow](./imgs/streaming_workflow.png)

</div>
</div>

This streaming workflow is achievable with the provided blueprint, however, it
requires additional setup and is not fully documented at this time.
We include it here as a reference to illustrate how we created the Blueprint
experience on the NVIDIA API catalog.

We encourage users that are interested in the streaming capabilities of Omniverse to
refer to the [WebRTC Browser Client Documentation](https://docs.omniverse.nvidia.com/extensions/latest/ext_livestream/webrtc.html)
for more information.

---
<div align="center">

| Previous | Next |
|:---------:|:-----:|
| [Readme](../README.md) | [Prerequisites](./01_prerequisites.md) |

</div>

# Earth-2 Weather Analytics Blueprint - Prerequisites

This document outlines the prerequisites for the Earth-2 Weather Analytics Blueprint.
The Earth-2 Weather Analytics Blueprint configures several components to serve as a reference implementation. This includes the Omniverse kit application, instance of DFM, an AI inference pipeline using a NIM. We show how these can be composed to work together so a developer can chose the relevant components and deploy them individually. 
The precise requirements depend on the final deployment configuration.

## Software

The following software is required for deployment and development of the blueprint:

- Ubuntu 22.04
- Docker - minimum version: 23.0.1
- NVIDIA Drivers - recommended version: 550.127.05
- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
  minimum version: 1.13.5
- [MicroKubernetes](https://microk8s.io/) - minimum version: 1.29.13

For the Omniverse Kit application, refer to the
[Omniverse Kit requirements documentation](https://docs.omniverse.nvidia.com/embedded-web-viewer/latest/common/technical-requirements.html).

For FourCastNet NIM requirements, refer to the
[Earth-2 NIM documentation](https://docs.nvidia.com/nim/earth-2/fourcastnet/latest/prerequisites.html).

Verify that docker is using the NVIDIA container runtime:

```bash
docker run --rm --runtime=nvidia --gpus all ubuntu nvidia-smi
```

### MicroK8s Setup

Verify that microk8s is ready and install the following addons:

```bash
microk8s start
microk8s status --wait-ready

microk8s enable helm
microk8s enable registry
microk8s enable ingress
microk8s enable dns

microk8s kubectl create namespace earth2
```

Install NVIDIA GPU Operator on MicroK8s. For detailed instructions, see the
[NVIDIA GPU Operator documentation](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html#procedure)
and respective [MicroK8s Configuration](https://docs.nvidia.com/datacenter/cloud-native/gpu-operator/latest/getting-started.html#microk8s).
In many instances you can just run:

```bash
microk8s enable gpu
```

Verify MicroK8s has access to GPU resources:

```bash
cat >cuda-vectoradd.yaml <<EOL
apiVersion: v1
kind: Pod
metadata:
  name: cuda-vectoradd
spec:
  restartPolicy: OnFailure
  containers:
  - name: cuda-vectoradd
    image: "nvcr.io/nvidia/k8s/cuda-sample:vectoradd-cuda11.7.1-ubuntu20.04"
    resources:
      limits:
        nvidia.com/gpu: 1
EOL
```

```bash
microk8s kubectl apply -f cuda-vectoradd.yaml
```

```bash
microk8s kubectl logs -f cuda-vectoradd

>>> [Vector addition of 50000 elements]
>>> Copy input data from the host memory to the CUDA device
>>> CUDA kernel launch with 196 blocks of 256 threads
>>> Copy output data from the CUDA device to the host memory
>>> Test PASSED
>>> Done
```

```bash
microk8s kubectl delete pod cuda-vectoradd
```

> For the remainder of this guide, we will work in the Kubernetes namespace `earth2`.
> Adjust the commands accordingly for different deployment environments.

To make the documentation k8s environment agnostic, we will use the following alias
going forward:

```bash
alias kubectl='microk8s kubectl'
alias helm='microk8s helm'
```

### Secrets and API Keys

Depending on the components deployed, certain API keys may be required and configured as
secrets in the Kubernetes cluster.

> The following are not required to deploy the most basic blueprint configuration.
> You may skip these steps if you are not interested in using these features
> and adjust your deployment accordingly.

#### Configure Private Docker Registry Secret

When using a private registry for pulling docker images (such as
[nvcr.io](https://docs.nvidia.com/launchpad/ai/base-command-coe/latest/bc-coe-docker-basics-step-02.html)),
an image pull credential may be required.
By default this is named `docker-secret` in the blueprint's Helm chart.
For example, the following command will create an image pull secret using a local
machine's docker credentials:

```bash
kubectl -n earth2 create secret generic docker-secret \
    --from-file=.dockerconfigjson=$HOME/.docker/config.json \
    --type=kubernetes.io/dockerconfigjson
```

#### Configure FourCastNet NIM API Key

As described in detail in the [FourCastNet NIM documentation](https://docs.nvidia.com/nim/earth-2/fourcastnet/latest/prerequisites.html#ngc-account),
an API key with NVIDIA AI Enterprise access is required to run the NIM.
One should both log in to nvcr.io as described above and set an image pull secret, as
well set a valid NGC API key as a secret that will allow the NIM to pull the FourCastNet
model weights.
To set up your credentials and create the secret, store your API key in the
`NGC_API_KEY` environment variable and run the following command:

```bash
kubectl -n earth2 create secret generic ngc-catalog-secret \
    --from-literal=api-key="${NGC_API_KEY}"
```

#### Configure ESRI API Key

The blueprint includes sample pipelines for fetching ESRI topographic data using the
[ArcGIS platform](https://www.esri.com/en-us/arcgis/geospatial-platform/overview).
To use this data, users need to provide private credentials through the
`esri-arcgis-secret` Kubernetes secret.
Set up your credentials and create the secret by storing your API key in the
`DFM_ESRI_API_KEY` environment variable and running the following command:

```bash
kubectl -n earth2 create secret generic esri-arcgis-secret \
    --from-literal=api-key="${DFM_ESRI_API_KEY}"
```

## Hardware

The following hardware recommendation pertain to deploying Earth-2 Command Center, Data
federation mesh, and FourCastNet NIM on the same node:

### Full Blueprint

- GPUs: 2x NVIDIA L40S 48 Gb
- CPU: 32 cores
- RAM: 64GB
- Storage: ≥128Gb NVMe SSD

The blueprint can be deployed on different hardware configurations, but some adjustment
to the helm charts will be required.
Since you may only be interested in certain components, individual hardware
requirements are listed below for each.

### Earth-2 OV Kit Application

Earth-2 OV Kit application requires an RTX-capable GPU. Use cards with larger memory
(RTX6000 or L40) for optimal performance.

#### Recommended Requirements

- GPUs: L40, L40S, RTX6000
- CPU: 16 cores
- RAM: ≥32GB
- Storage: 16Gb NVMe SSD

Refer to the [Omniverse Kit documentation](https://docs.omniverse.nvidia.com/embedded-web-viewer/latest/common/technical-requirements.html)
for more information.

### Data Federation Mesh

The Data Federation Mesh (DFM) implementation, consists of a series of
containers that provide data processing and caching capabilities to the blueprint.
The recommended hardware requirements for Data Federation Mesh are:

#### Recommended Requirements

- CPU: 4 cores
- RAM: 16GB
- Storage: 64Gb NVMe SSD

> Storage size depends greatly on the desired workflow and amount of data that is expected
> to get cached.

### FourCastNet NIM

See the [FourCastNet NIM documentation](https://docs.nvidia.com/nim/earth-2/fourcastnet/latest/prerequisites.html#hardware-support)
for detailed hardware requirements.

<!-- Footer Navigation -->
---
<div align="center">

| Previous | Next |
|:---------:|:-----:|
| [Workflow](./00_workflow.md) | [Quickstart](./02_quickstart.md) |

</div>

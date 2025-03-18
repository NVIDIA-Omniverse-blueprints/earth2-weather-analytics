# Earth-2 Weather Analytics Blueprint - Troubleshooting

This section describes common issues and their solutions for the Earth-2 Weather
Analytics Blueprint.

## Deployment

### How do I remove MicroK8s images?

Sometimes it is useful to clean up the MicroK8s images to ensure new builds are installed
or to free disk space after tearing down the deployment.

To remove all the blueprint images on MicroK8s registry use the following script:

```bash
sudo microk8s ctr images ls name~='earth2-weather-analytics' | awk {'print $1'} > image_ls
# loop over file, remove each image
cat image_ls | while read line || [[ -n $line ]];
do
    microk8s ctr images rm $line
done;
```
<!-- markdownlint-disable MD013 -->
### MircoK8s commands error `tls: failed to verify certificate: x509: certificate is valid for`
<!-- markdownlint-enable MD013 -->

Try refreshing the TLS certificate:

```bash
sudo microk8s refresh-certs --cert ca.crt
```

### Redis pods are not starting up / cannot connect

Issues with networking between pods can cause problems during the deployment of the
blueprint or during runtime.
One common problem is that the DNS is configured incorrectly.
**Use with caution** as this will remove all the data from MicroK8s, including all the
data from the blueprint.
Try resetting the DNS configuration with:

```bash
# Stop microk8s
sudo microk8s stop

# Remove DNS-related configurations
sudo rm -rf /var/snap/microk8s/current/args/cni-network/
sudo rm -rf /var/snap/microk8s/current/args/coredns/

# Remove the snap and reinstall it
sudo snap remove microk8s
sudo snap install microk8s --classic

# Wait for microk8s to be ready
microk8s status --wait-ready

# Complete the steps in the prerequisites section
```

### My MicroK8s cluster is having other issues, how do I fix them?

Start by checking the [Official MicroK8s Troubleshooting Documentation](https://microk8s.io/docs/troubleshooting).

As a last resort, you can perform a complete reinstall of MicroK8s to have a clean
kubernetes environment.
Sometime this can be the best course of action to fix underlying issues with the
kubernetes cluster.
**Use with caution** as this will remove all the data from MicroK8s, including all the
data from the blueprint.

```bash
sudo snap remove microk8s --purge
sudo snap install microk8s --classic
```

## Earth-2 Command Center

E2CC provides a lot of information about what is happening in the console logs.
Users are encouraged to watch the logs when unexpected behavior is observed.

### My changes in E2CC are not reflected in the application

If you make changes to the E2CC source code and they are not reflected in the
application, you may need to perform a clean build of the application.

```bash
rm -rf e2cc/_build
rm -rf e2cc/_repo

./build.sh --release
```

### E2CC is consuming too much memory

E2CC uses the dynamic texture extension which has an in-memory cache
to help to ensure smooth playback and scrubbing of long
time sequences of two-dimensional data sets.
If you have less than the recommended amount of host memory, you can adjust the cache
size using the command line parameter:

```bash
--/exts/omni.earth_2_command_center.app.setup/dynamic_texture_cache_size=1000000000
```

The `dynamic_texture_cache_size` value is given in bytes.

### E2CC does not properly visualize the globe on shader recompile

This is commonly seen if you are running an incorrect driver version.
Please ensure you are running a driver version of 550.127.05 or one of the drivers
explicitly supported by Omniverse.
Newer drivers are not guaranteed to work.

### E2CC pipelines immediately fail with error `Cannot connect to host localhost:8080`

This issue is seen when the E2CC application cannot connect to the data federation
mesh service.
The error message in the console will be:

<!-- markdownlint-disable MD013 -->
```bash
2025-03-10 01:23:33 [15,639ms] [Error] [omni.earth_2_command_center.app.dfm.utils.dfm] Cannot connect to host localhost:8080 ssl:default [Connect call failed ('127.0.0.1', 8080)]
2025-03-10 01:23:33 [15,640ms] [Error] [omni.earth_2_command_center.app.dfm_ui.ui.main] Something unexpected went wrong: ClientConnectorError.with_traceback() takes exactly one argument (0 given)
```
<!-- markdownlint-enable MD013 -->

By default, the application will try to connect to the service at `localhost:8080`.
If you are following the standard deployment procedure, ensure that the DFM process
service is exposed to the host network.
One method is to port forward the service to a local port:

```bash
kubectl -n earth2 port-forward service/earth2-weather-analytics-process 8080:8080
```

If the service is being exposed on a different port, you can change where E2CC looks by
changing the environment variables:

```bash
export K8S_E2CC_DFM_PROCESS_HOST=127.0.0.1
export K8S_E2CC_DFM_PROCESS_PORT=8080
```

### E2CC submits pipelines but cannot find the produced textures

This common deployment issue results in an error similar to the following:

<!-- markdownlint-disable MD013 -->
```bash
2025-03-10 01:36:32 [78,837ms] [Error] [omni.earth_2_command_center.app.dfm.utils.dfm] Texture file not found, is your cache location correct? /wrong-cache-location/textures/dfm_cache_5e62d6109ec9c960194c8920fd65288bcc2c2422bd72e474f89d3e8f0df0aa61/2024-01-01T00C00_u10m.jpeg
2025-03-10 01:36:32 [78,837ms] [Error] [omni.earth_2_command_center.app.dfm_ui.ui.main] Something unexpected went wrong: FileExistsError.with_traceback() takes exactly one argument (0 given)
```
<!-- markdownlint-enable MD013 -->

This means that the texture cache location used by E2CC and DFM are not consistent.
When deploying the blueprint, this cache location is set by the volume section:

```yaml
volumes:
  - name: cache-volume
    hostPath:
      path: /cache
      type: Directory
```

In this example, the cache folder will be `/cache` on the host machine.
This is the default location E2CC will look for, but one can change this by setting
the `E2CC_CACHE_PATH` environment variable before launching the application:

```bash
export E2CC_CACHE_PATH=/cache
```

### E2CC fetch produces `Pipeline already running!`

This indicates that a data pipeline was previously submitted and is actively running.
Check the console log of E2CC to see if there is a console message indicating the
pipeline was submitted to the data federation mesh.
Currently, the blueprint limits the number of concurrent requests to prevent
users from downloading large amounts of data unintentionally.
Give the job a few minutes to pull data (or potentially timeout).
If the job remains stalled for over 10 minutes with no updates, kill E2CC and relaunch.

> [!NOTE]
> While the UI and blueprint extension in E2CC limit the number of concurrent
> DFM pipelines to just one, this is imposed to protect the user initially and
> can be removed by developers. DFM was designed to handle multiple job requests.

## Data Federation Mesh

Data Federation Mesh is a set of services running inside Micro Kubernetes, so debugging
and troubleshooting should follow normal debugging procedures for K8s microservices,
like examining logs and checking pods state. Check
[Kubernetes documentation](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
to learn more about common debugging methods.

DFM deployments should have at least the following pods running:

```bash
$ microk8s kubectl -n earth2 get pods
NAME                                                   READY  STATUS   RESTARTS  AGE
weather-analytics-blueprint-execute-75fb6c9bfc-tfrqp   1/1    Running  0         2d3h
weather-analytics-blueprint-process-696bc75766-hdclv   1/1    Running  0         2d3h
weather-analytics-blueprint-redis-master-0             1/1    Running  0         2d3h
weather-analytics-blueprint-redis-replicas-0           1/1    Running  0         2d3h
weather-analytics-blueprint-scheduler-666ff9999c-mrqqw 1/1    Running  0         2d3h
```

To run basic tests, please read about port forwarding and basic Micro8ks operations
in [MicroK8s Deployment](03_microk8s_deployment.md).

The most basic check is verification of connectivity and Process service responsiveness:

```bash
curl localhost:8080/version
```

To run more elaborate tests, that involve executing a DFM pipeline by Execute service,
use pipeline examples:

```bash
python3 helper/pipelines/era5.py
```

Check logs from Execute service (`weather-analytics-blueprint-execute-75fb6c9bfc-tfrqp` above)
for errors.
One very common problem is the lack of necessary API keys required to access services
such as ESRI data.

DFM requests can also fail due to transient errors, such as data sources being
unavailable.
This should be a rare occurrence, since most of the requests should be served from
the internal DFM cache.

The DFM cache is mapped to the host disk (see [MicroK8s Deployment](03_microk8s_deployment.md)).
If you run into low disk space issues,

1. Stop the MicroK8s deployment: `microk8s stop`
1. Clean up the cache: `rm -rf $(pwd)/cache`
1. Restart the MicroK8s deployment: `microk8s start`

In other cases, usually restarting pods or redeploying services helps clearing any
errors.

## FourCastNet NIM

### My FourCastNet NIM cannot download the model weights

Upon start-up, the FourCastNet NIM container will download the model weights from Nvidia
GPU Cloud (NGC).
This requires an `NGC API key` that has Nvidia AI Enterprise catalog access.
The NIM container failing to pull the weights indicates that the API key is invalid or
the API key has not been set.
The NIM container will use the environment variable `NGC_API_KEY` which can be set with
the blueprint helm chart by two methods:

1. Set your NGC API key as the K8s secret `nim-api-key`.
1. Set your NGC API key as the `nim.overrideNgcAPIKey=<NGC_API_KEY>` helm value on
    deployment.

> [!NOTE]
> When deploying on NVCF, the NGC API key can be provided by providing a function secret
> with the name `NGC_API_KEY`.

<!-- Footer Navigation -->
---
<div align="center">

| Previous | Next |
|:---------:|:-----:|
| [Sequence Diagram](./06_sequence.md) | [Readme](../README.md) |

</div>

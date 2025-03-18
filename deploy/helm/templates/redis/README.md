# Redis Template for NVCF

> This template should only be used when deploying in NVCF. Otherwise, users are
> encouraged to use the Bitnami chart directly which is the default.

This is an extracted template based on the [Bitnami Redis chart](https://github.com/bitnami/charts/tree/main/bitnami/redis).
Due to the restrictions of NVCF, we cannot use the Bitnami chart directly thus
implement a seperate template.
Most of the required modifications can be done using Bitnami's helm options, however
some require manual editting.
The original chart yamls were extracted using the following helm template command:

```bash
helm template myreleasename -n mynamespace --debug
```

The redis specific components were then extracted using.
The following modifications were then made for NVCF compatibility:

- Use the NGC container registry for the Redis image
- Update image pull secrets to use the NGC image pull secret
- Removed references to service accounts which are not supported in NVCF

For more information of what requirements NVCF has for running helm charts, see the
[NVCF Documentation](https://docs.nvidia.com/cloud-functions/user-guide/latest/cloud-function/overview.html).

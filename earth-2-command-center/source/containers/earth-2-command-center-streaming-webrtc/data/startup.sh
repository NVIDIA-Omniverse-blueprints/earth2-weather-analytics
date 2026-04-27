#!/usr/bin/env bash
set -e
set -u

# Check for libGLX_nvidia.so.0 (needed for vulkan)
ldconfig -p | grep libGLX_nvidia.so.0 || NOTFOUND=1
if [[ -v NOTFOUND ]]; then
    cat << EOF > /dev/stderr

Fatal Error: Can't find libGLX_nvidia.so.0...

Ensure running with NVIDIA runtime. (--gpus all) or (--runtime nvidia)

EOF
    exit 1
fi

# Detect NVIDIA Vulkan API version, and create ICD:
export VK_ICD_FILENAMES=/tmp/nvidia_icd.json

E2CC_DOWNLOAD_INDEX_DATA="${E2CC_DOWNLOAD_INDEX_DATA:-"0"}"

if [[ $E2CC_DOWNLOAD_INDEX_DATA == "1" ]]; then
    /opt/nvidia/omniverse/earth-2-command-center/get-index-data.sh
fi

USD_PATH="${USD_PATH:-""}"

USER_ID="${USER_ID:-""}"
if [ -z "${USER_ID}" ]; then
  echo "User id is not set"
fi

WORKSTREAM="${OV_WORKSTREAM:-"earth-2"}"
SHELL="${OV_SHELL:-0}"
if [ "${SHELL}" == "1" ]; then
  echo "Running in shell mode"
  tail -f /dev/null
fi

export HSSC_SC_MEMCACHED_SERVICE_NAME="memcached-service-r3"
export HSSC_SC_MEMCACHED_REDISCOVER="1"
export HSSC_SC_CLIENT_LOGFILE_ROOT=/tmp/renders/hssc
mkdir -p /tmp/renders

__GL_F32B90a0=$(find /opt/nvidia/omniverse/hssc_shader_cache_client_lib -path \*release/lib\* -name libhssc_shader_cache_client.so)
echo "Found hssc client so in: $__GL_F32B90a0"
export __GL_F32B90a0
export __GL_a011d7=1   # OGL_VULKAN_GFN_SHADER_CACHE_CONTROL=ON
export __GL_43787d32=0 #  OGL_VULKAN_SHADER_CACHE_TYPE=NONE
export __GL_3489FB=1   # OGL_VULKAN_IGNORE_PIPELINE_CACHE=ON

export OPENBLAS_NUM_THREADS=10 # OM-97400, optimize thread count for numpy(OpenBlas)

CMD="/opt/nvidia/omniverse/earth-2-command-center/omni.earth_2_command_center.app_ovc.sh"
ARGS=(
    "--no-window"
    "--/privacy/userId=${USER_ID}"
    "--/crashreporter/data/workstream=${WORKSTREAM}"
    # No idea how to set empty/null value in `omni.earth_2_command_center.app.kit`, so keep it as it
    "--/exts/omni.kit.window.content_browser/show_only_collections/2=" # OM-98801
    "--/exts/omni.kit.window.filepicker/show_only_collections/2=" # OM-98801
    "--/exts/omni.kit.registry.nucleus/registries/0/url=https://ovextensionsprod.blob.core.windows.net/exts/kit/integ/105.0-a2b6befb/shared"
    "--/exts/omni.kit.registry.nucleus/registries/1/url="
    "--ext-folder /home/ubuntu/.local/share/ov/data/exts/v2"
    "--/crashreporter/gatherUserStory=0" # Workaround for OMFP-2908 while carb fix is deployed.
    "--/crashreporter/includePythonTraceback=0" # Workaround for OMFP-2908 while carb fix is deployed.
)

# Since we won't have access for
export OVC_KIT=/opt/nvidia/omniverse/earth-2-command-center/apps/omni.earth_2_command_center.app.kit
echo "==== Print out kit config ${OVC_KIT} for debugging ===="
cat ${OVC_KIT}
echo "==== End of kit config ${OVC_KIT} ===="

# If $KIT_ARGS_OVERRIDE env is set it replaces the default args
KIT_ARGS_OVERRIDE="${KIT_ARGS_OVERRIDE:-""}"
if [[ -z "${KIT_ARGS_OVERRIDE}" ]]; then
    for arg in "${ARGS[@]}"
    do
        CMD="$CMD $arg"
    done
else
    CMD="$CMD $(eval echo $KIT_ARGS_OVERRIDE)"
fi

# Append extra kit args from the env variable $KIT_EXTRA_ARGS
KIT_EXTRA_ARGS="${KIT_EXTRA_ARGS:-""}"
CMD="$CMD $(eval echo $KIT_EXTRA_ARGS)"

# Apply patch for problematic NVPARK ingress IPs returned by DNS
sleep 60
echo "10.120.32.42	execute-earth-2.sc-paas.nvidia.com" | sudo tee -a /etc/hosts
echo "10.120.32.43  execute-earth-2-dev.sc-paas.nvidia.com" | sudo tee -a /etc/hosts

echo "Starting Earth 2 Command Center with $CMD $@"

CMD="exec $CMD $@"

eval $CMD

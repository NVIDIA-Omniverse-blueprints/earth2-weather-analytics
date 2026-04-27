FROM gitlab-master.nvidia.com:5005/omniverse/containers/apps/ov-packman/ov-packman:latest as kit-build

# Shader caches and a util script
ARG HSSC_SHADER_CACHE_VERSION=0.1.4+mr.0.cb1ac7dc.local.linux-x86_64
RUN /opt/nvidia/packman/packman install hssc_shader_cache_client_lib ${HSSC_SHADER_CACHE_VERSION}

# Runtime image
FROM gitlab-master.nvidia.com:5005/omniverse/containers/apps/ov-base/ov-base-ubuntu-22:2024.5.0

# Switch to root user
USER root

# This is bad - we need to enable sudo to add entries to /etc/host in startup.sh
# It's not possible to add the entry here - buildkit prevents overwritting /etc/hosts
# And we need this WA until we sort out DNS/connectivity issues between pods in PRD31 and NVPARK.
RUN echo "deb http://us.archive.ubuntu.com/ubuntu/ jammy main restricted" >> /etc/apt/sources.list

RUN echo "ubuntu ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Copy main packages from previous build stages
COPY _build/packages/ /opt/nvidia/omniverse/earth-2-command-center/

WORKDIR /opt/nvidia/omniverse/earth-2-command-center/
RUN PACKAGE_FILE=$(find . -type f -name "*.release.zip") && unzip $PACKAGE_FILE -d . && rm $PACKAGE_FILE

# Install runtime configuration files
ARG LOCAL_DATA_PATH=source/containers/earth-2-command-center-streaming-webrtc/data

COPY ${LOCAL_DATA_PATH}/10_nvidia.json     /usr/share/glvnd/egl_vendor.d/10_nvidia.json
COPY ${LOCAL_DATA_PATH}/50_mesa.json       /usr/share/glvnd/egl_vendor.d/50_mesa.json
COPY ${LOCAL_DATA_PATH}/nvidia_icd.json    /etc/vulkan/icd.d/nvidia_icd.json
COPY ${LOCAL_DATA_PATH}/nvidia_icd.json    /tmp
COPY ${LOCAL_DATA_PATH}/nvidia_layers.json /etc/vulkan/implicit_layer.d/nvidia_layers.json
COPY ${LOCAL_DATA_PATH}/startup.sh         /startup.sh
COPY ${LOCAL_DATA_PATH}/get-index-data.sh  /opt/nvidia/omniverse/earth-2-command-center/get-index-data.sh
COPY ${LOCAL_DATA_PATH}/get_index_data.py  /opt/nvidia/omniverse/earth-2-command-center/get_index_data.py

COPY --from=kit-build /var/tmp/packman/chk/hssc_shader_cache_client_lib/${HSSC_SHADER_CACHE_VERSION}/ /opt/nvidia/omniverse/hssc_shader_cache_client_lib

RUN rm /root/.pip/pip.conf

# OVCC-1351
RUN rm -rf /home/ubuntu/.nvidia-omniverse/logs/*
# Fix permission for shadercache generation
RUN chown -R ubuntu /opt/nvidia/

# Switch back to non-root user
USER ubuntu

RUN mkdir -p /home/ubuntu/.nvidia-omniverse/config
RUN /opt/nvidia/omniverse/earth-2-command-center/pull_kit_sdk.sh

# Since the command will create kit folder and copy file into it, the `pull_kit_sdk.sh` kit (kit-kernel) downloading process will be blocked.
# So we need to put the line after the pull_kit_sdk.sh executed.
COPY ${LOCAL_DATA_PATH}/server_side_nvscClientConfig.txt /opt/nvidia/omniverse/earth-2-command-center/kit/server_side_nvscClientConfig.txt

# Open ports for live streaming
EXPOSE 47995-48012/udp \
    47995-48012/tcp \
    49000-49007/udp \
    49000-49007/tcp \
    8011/tcp \
    8111/tcp \
    49100/tcp

ENTRYPOINT ["/startup.sh"]

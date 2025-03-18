#!/bin/bash

# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: LicenseRef-NvidiaProprietary
#
# NVIDIA CORPORATION, its affiliates and licensors retain all intellectual
# property and proprietary rights in and to this material, related
# documentation and any modifications thereto. Any use, reproduction,
# disclosure or distribution of this material and related documentation
# without an express license agreement from NVIDIA CORPORATION or
# its affiliates is strictly prohibited.


set -e

function help() {
    echo "Usage:"
    echo "    $0 [-m] [-k] [-f] [--nvcr]"
    echo "      -k - Prepare images for Microk8s environment"
    echo "      -f - Force rebuild images even if they exist"
    echo "      --nvcr - Use NVIDIA Ubuntu base image instead of default Docker Hub Ubuntu"
}

function image_exists_in_microk8s() {
    local image_name=$1
    microk8s ctr images ls | grep -q "$image_name"
    return $?
}

force_rebuild=0
use_nvcr=0

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        -k)
            use_microk8s=1
            shift
            ;;
        -f)
            force_rebuild=1
            shift
            ;;
        -h)
            help
            exit 0
            ;;
        --nvcr)
            use_nvcr=1
            shift
            ;;
        *)
            help
            exit 1
            ;;
    esac
done

# Define service directories and their corresponding image names
declare -A service_to_image=(
    ["execute"]="earth2-weather-analytics-execute"
    ["process"]="earth2-weather-analytics-process"
    ["scheduler"]="earth2-weather-analytics-scheduler"
)
declare -a extra_images=("redis/redis-stack-server:7.2.0-v11")
image_tag="0.1.0"

# Set base image based on --nvcr flag
if [[ $use_nvcr -eq 1 ]]; then
    base_image="nvcr.io/nvidia/base/ubuntu:22.04_20240212"
else
    base_image="ubuntu:22.04"
fi

# Iterate over the service-to-image mapping
for service_dir in "${!service_to_image[@]}"; do
    image=${service_to_image[$service_dir]}
    service_path="src/k8s/$service_dir"
    echo "Building $image from $service_path"
    image_name=$image:$image_tag

    if [[ $use_microk8s ]]; then
        if [[ $force_rebuild -eq 0 ]] && image_exists_in_microk8s "$image_name"; then
            echo "Image $image_name already exists in microk8s, skipping build"
            continue
        fi
        echo "Building $image_name for microk8s"
        docker build -f ${service_path}/Dockerfile --build-arg BASE_IMAGE=${base_image} -t $image_name .
        echo "Importing $image_name to microk8s"
        docker save $image_name > /tmp/${image}_${image_tag}.tar
        microk8s ctr image import /tmp/${image}_${image_tag}.tar
        rm /tmp/${image}_${image_tag}.tar
    else
        echo "Building $image_name in docker"
        docker build -f ${service_path}/Dockerfile --build-arg BASE_IMAGE=${base_image} -t $image_name .
    fi
done

if [[ $use_microk8s ]]; then
    for image in "${extra_images[@]}"; do
        if [[ $force_rebuild -eq 0 ]] && image_exists_in_microk8s "$image"; then
            echo "Image $image already exists in microk8s, skipping import"
            continue
        fi
        echo "Loading $image to Microk8s..."
        docker pull $image
        docker save $image > /tmp/extra_image.tar
        microk8s ctr image import /tmp/extra_image.tar
        rm /tmp/extra_image.tar
    done
fi

echo "Done building images!"

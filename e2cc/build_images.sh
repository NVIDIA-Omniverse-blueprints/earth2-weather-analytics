#!/bin/bash

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Builds Omniverse streamer image
TAG="0.1.0"
NAME="earth2-weather-analytics-streamer"
use_microk8s=0  # Default to not using microk8s
force_rebuild=1

# Function to show help
help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -k            Use microk8s"
    echo "  --tag TAG     Set image tag"
    echo "  --name NAME   Set image name"
}

# Function to check if image exists in microk8s
image_exists_in_microk8s() {
    local image=$1
    microk8s ctr images ls -q | grep -q "$image"
    return $?
}

while [[ $# -gt 0 ]]; do
    case $1 in
        -k)
            use_microk8s=1
            shift
            ;;
        --tag)
            TAG="$2"
            shift 2
            ;;
        --name)
            NAME="$2"
            shift 2
            ;;
        -h|--help)
            help
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

echo "Forcing clean rebuild..."
rm -rf "${SCRIPT_DIR}/_build" "${SCRIPT_DIR}/_repo" "${SCRIPT_DIR}/_compiler"

"${SCRIPT_DIR}/build.sh" --release

sleep 1

"${SCRIPT_DIR}/repo.sh" package_app \
    --container \
    --target-app omni.earth_2_command_center.app_nvcf.kit \
    --name kit_earth_2_command_center \
    --image-tag ${NAME}:${TAG}

# Add microk8s image handling
if [[ $use_microk8s -eq 1 ]]; then
    image="${NAME}:${TAG}"
    if [[ $force_rebuild -eq 0 ]] && image_exists_in_microk8s "$image"; then
        echo "Image $image already exists in microk8s, skipping import"
    else
        echo "Loading $image to Microk8s..."
        docker save $image > /tmp/streamer_image.tar
        microk8s ctr image import /tmp/streamer_image.tar
        rm /tmp/streamer_image.tar
    fi
fi
#!/bin/bash

# Retags and pushes images to NGC
ngc_registry="nvcr.io/"
tag=""
source_tag="0.1.0"

# Function to display help
function help() {
    echo "Usage: $0 --tag <tag> [--registry <registry>]"
    echo "  --tag      Required: Tag for the images"
    echo "  --registry Optional: NGC registry (default: nvcr.io/)"
    exit 1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --tag)
            tag="$2"
            shift 2
            ;;
        --registry)
            ngc_registry="$2"
            shift 2
            ;;
        -h|--help)
            help
            ;;
        *)
            help
            ;;
    esac
done

# Check if tag is provided
if [ -z "$tag" ]; then
    echo "Error: --tag parameter is required"
    help
fi

# Array of image names
declare -a images=(
    "earth2-weather-analytics-streamer"
    "earth2-weather-analytics-process"
    "earth2-weather-analytics-execute"
    "earth2-weather-analytics-scheduler"
)

# Function to retag and push an image
retag_and_push() {
    local source_image="$1:$source_tag"
    local target_image="$ngc_registry/$1:$tag"

    echo "Retagging $source_image to $target_image"
    docker tag "$source_image" "$target_image"

    echo "Pushing $target_image"
    docker push "$target_image"

    if [ $? -eq 0 ]; then
        echo "Successfully pushed $target_image"
    else
        echo "Failed to push $target_image"
        exit 1
    fi
}

# Process each image
for image in "${images[@]}"; do
    retag_and_push "$image"
done

echo "All images have been retagged and pushed successfully"

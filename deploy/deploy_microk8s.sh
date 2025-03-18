#!/bin/bash

set -e  # Exit on any error

# Default values - ensure absolute path
CACHE_PATH="$(pwd)/cache"

# Function to validate and create cache directory
validate_cache_path() {
    local path="$1"

    # Check if path exists
    if [ -d "$path" ]; then
        # Check if directory is writable
        if [ -w "$path" ]; then
            echo "Using existing cache directory: $path"
            return 0
        else
            echo "Error: Cache directory exists but is not writable: $path"
            return 1
        fi
    else
        # Try to create the directory
        echo "Creating cache directory: $path"
        if mkdir -p "$path" 2>/dev/null; then
            echo "Successfully created cache directory"
            return 0
        else
            echo "Error: Failed to create cache directory: $path"
            return 1
        fi
    fi
}

# Help message
function help() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -c, --cache-path PATH    Path to cache directory (default: ${CACHE_PATH})"
    echo "  -w, --wait              Wait for pods to be ready"
    echo "  -f, --force             Force rebuild of images"
    echo "  -n, --no-nim           Disable NIM deployment"
    echo "  --skip-build           Skip building docker images"
    echo "  -h, --help              Show this help message"
}

# Add wait, force, and no-nim flags
WAIT=false
FORCE=false
DISABLE_NIM=false
SKIP_BUILD=false

# Parse arguments and convert to absolute path if needed
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--cache-path)
            CACHE_PATH="$2"
            if [[ "$CACHE_PATH" != /* ]]; then
                CACHE_PATH="$(pwd)/${CACHE_PATH}"
            fi
            shift 2
            ;;
        -w|--wait)
            WAIT=true
            shift
            ;;
        -f|--force)
            FORCE=true
            shift
            ;;
        -n|--no-nim)
            DISABLE_NIM=true
            shift
            ;;
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        -h|--help)
            help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            help
            exit 1
            ;;
    esac
done

echo "Using cache path: ${CACHE_PATH}"
if ! validate_cache_path "$CACHE_PATH"; then
    echo "Cache path validation failed. Exiting."
    exit 1
fi

# Build required images
if [ "$SKIP_BUILD" = false ]; then
    echo "Building required images..."
    if [ "$FORCE" = true ]; then
        ./src/build_images.sh -k -f
    else
        ./src/build_images.sh -k
    fi
else
    echo "Skipping image build..."
fi

# Clean up any existing port forwards
echo "Cleaning up any existing port forwards..."
pkill -f "port-forward" || true
jobs -p | xargs -r kill || true

sleep 1

# Enable required MicroK8s addons
echo "Ensuring MicroK8s is ready..."
microk8s status --wait-ready
# Ensure all needed addons are enabled
microk8s enable gpu
microk8s enable helm
microk8s enable registry
microk8s enable ingress
microk8s enable dns

# Create namespace if it doesn't exist
echo "Setting up namespace..."
microk8s kubectl create namespace earth2 || true

# Set up docker registry secret if it doesn't exist
if ! microk8s kubectl -n earth2 get secret docker-secret &> /dev/null; then
    echo "Creating docker registry secret..."
    microk8s kubectl -n earth2 create secret generic docker-secret \
        --from-file=.dockerconfigjson=$HOME/.docker/config.json \
        --type=kubernetes.io/dockerconfigjson
fi

if ! microk8s kubectl -n earth2 get secret esri-arcgis-secret &> /dev/null && [ -n "${DFM_ESRI_API_KEY}" ]; then
    echo "Creating ESRI ArcGIS secret..."
    microk8s kubectl -n earth2 create secret generic esri-arcgis-secret \
        --from-literal=api-key="${DFM_ESRI_API_KEY}"
fi

# Set up NGC credentials if NGC_API_KEY is provided
if [ -n "${NGC_API_KEY}" ]; then
    echo "Setting up NGC credentials..."
    # Create NGC catalog secret
    microk8s kubectl -n earth2 create secret generic ngc-catalog-secret \
        --from-literal=api-key="${NGC_API_KEY}" || true

    # Create NGC registry secret
    microk8s kubectl -n earth2 create secret docker-registry ngc-registry-secret \
        --docker-server=nvcr.io \
        --docker-username='$oauthtoken' \
        --docker-password="${NGC_API_KEY}" || true
else
    echo "Warning: NGC_API_KEY not set. NIM deployment may fail without NGC credentials."
fi

# Uninstall existing helm chart if it exists, then install/reinstall
if microk8s helm list -n earth2 | grep -q "earth2-weather-analytics"; then
    echo "Uninstalling existing deployment..."
    microk8s helm uninstall -n earth2 earth2-weather-analytics
    # Wait for resources to be cleaned up
    sleep 10
    # Potential useful to force delete, but dangerous
    # for p in $(kubectl get pods -n earth2 | grep Terminating | awk '{print $1}'); do kubectl delete pod -n earth2 $p --grace-period=0 --force;done

fi

echo "Building helm dependencies..."
microk8s helm dependency build deploy/helm/

echo "Installing helm chart..."
microk8s helm install -n earth2 earth2-weather-analytics deploy/helm \
    -f deploy/helm/values.dev.yaml \
    --set volumes[0].hostPath.path=${CACHE_PATH} \
    --set nim.enabled=$([ "$DISABLE_NIM" = true ] && echo "false" || echo "true")

if [ "$WAIT" = true ]; then
    echo "Waiting for all pods to be ready..."
    # Small delay to let k8s catch up
    sleep 5

    # Wait for Redis
    echo "Waiting for Redis..."
    microk8s kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=redis -n earth2 --timeout=300s

    # Wait for Process
    echo "Waiting for Process pod..."
    microk8s kubectl -n earth2 wait --for=condition=ready pod -l app.kubernetes.io/component=process --timeout=300s

    # Wait for Scheduler
    echo "Waiting for Scheduler pod..."
    microk8s kubectl -n earth2 wait --for=condition=ready pod -l app.kubernetes.io/component=scheduler --timeout=300s

    # Wait for Execute
    echo "Waiting for Execute pod..."
    microk8s kubectl -n earth2 wait --for=condition=ready pod -l app.kubernetes.io/component=execute --timeout=300s
else
    # Original wait
    echo "Waiting for deployment to be ready..."
    sleep 120
fi

microk8s kubectl -n earth2 get pods

echo "Setting up port forward of earth2-weather-analytics-process API..."
# Clean up any existing port forwards again before setting up new one
pkill -f "port-forward" || true
jobs -p | xargs -r kill || true
# Start port forward in background and save PID
sleep 5
microk8s kubectl -n earth2 port-forward service/earth2-weather-analytics-process 8080:8080 &
PORT_FORWARD_PID=$!

# Give it time to start
sleep 5

echo "Verifying deployment..."
CURL_OUTPUT=$(curl -s localhost:8080/version)
CURL_STATUS=$?

# Clean up port forward immediately
kill $PORT_FORWARD_PID 2>/dev/null || true
wait $PORT_FORWARD_PID 2>/dev/null || true

if [ $CURL_STATUS -ne 0 ]; then
    echo "Failed to verify deployment: curl command failed"
    exit 1
fi

# Check if output contains error
if echo "$CURL_OUTPUT" | grep -q "error"; then
    echo "Failed to verify deployment: API returned error"
    echo "Response: $CURL_OUTPUT"
    exit 1
fi

# Validate that we got a proper version response (should contain version field)
if ! echo "$CURL_OUTPUT" | grep -q "version"; then
    echo "Failed to verify deployment: Invalid version response"
    echo "Response: $CURL_OUTPUT"
    exit 1
fi

echo "Deployment verification output:"
echo "$CURL_OUTPUT"
echo "Deployment successful!"
exit 0

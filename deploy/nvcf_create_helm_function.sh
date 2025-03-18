#!/bin/bash

# A script to create a new helm Nvidia Cloud function in the NGC CLI

# Check if .env file exists in the current directory
if [ -f .env ]; then
  echo ".env file found. Loading environment variables..."
  # Source the .env file to export the environment variables
  set -o allexport
  source .env
  set +o allexport
else
  echo ".env file not found. Skipping loading environment variables."
fi


if [ -z "${NGC_CLI_API_KEY:+x}" ]; then
    echo "NGC_CLI_API_KEY must be set"
    exit 1
fi

if [ -z "${HELM_CHART_URL:+x}" ]; then
    echo "HELM_CHART_URL must be set"
    exit 1
fi

if [ -z "${HELM_CHART_SERVICE:+x}" ]; then
    HELM_CHART_SERVICE="streamer-entrypoint"
    echo "HELM_CHART_SERVICE not set, using default: "$HELM_CHART_SERVICE
fi

if [ -z "${NVCF_FUNCTION_NAME:+x}" ]; then
    NVCF_FUNCTION_NAME="earth-2-weather-analytics-blueprint"
    echo "NVCF_FUNCTION_NAME not set, using default: "$NVCF_FUNCTION_NAME
fi

if [ -z "${STREAMING_SERVER_PORT:+x}" ]; then
    STREAMING_SERVER_PORT=49100
    echo "STREAMING_SERVER_PORT not set, using default: "$STREAMING_SERVER_PORT
fi

if [ -z "${HTTP_SERVER_PORT:+x}" ]; then
    HTTP_SERVER_PORT=8011
    echo "HTTP_SERVER_PORT not set, using default: "$HTTP_SERVER_PORT
fi

if [ -z "${NGC_CLI_API_URL:+x}" ]; then
    # For staging, use api.stg.ngc.nvidia.com
    NGC_CLI_API_URL=api.ngc.nvidia.com
    echo "NGC_CLI_API_URL not set, using default: "$NGC_CLI_API_URL
fi

# NOTE: assume that NVCF_SECRETS are already in double quote
response=$(curl -s --location --request POST 'https://'$NGC_CLI_API_URL'/v2/nvcf/functions' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer '$NGC_CLI_API_KEY'' \
--data '{
  "name": "'$NVCF_FUNCTION_NAME'",
  "inferenceUrl": "/sign_in",
  "inferencePort": '$STREAMING_SERVER_PORT',
  "health": {
    "protocol": "HTTP",
    "uri": "/v1/streaming/ready",
    "port": '$HTTP_SERVER_PORT',
    "timeout": "PT10S",
    "expectedStatusCode": 200
  },
  "helmChart": "'$HELM_CHART_URL'",
  "helmChartServiceName": "'$HELM_CHART_SERVICE'",
  "apiBodyFormat": "CUSTOM",
  "description": "'$NVCF_FUNCTION_NAME'",
  "functionType": "STREAMING"
}
')

function_id=$(echo $response | jq -r '.function.id')
function_version_id=$(echo $response | jq -r '.function.versionId')

echo "============================="
echo "Function Updated Successfully"
echo "Function ID: "$function_id
echo "Function Version ID: "$function_version_id
echo "============================="

echo $response

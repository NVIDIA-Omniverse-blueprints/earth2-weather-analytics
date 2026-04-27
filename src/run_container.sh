#!/usr/bin/env bash
set -e

# Build from repo root so Docker context includes earth-2-federation/dist
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

docker build --network=host -f src/Dockerfile -t earth2-blueprint-app .  #--no-cache
docker run --gpus=all --name earth2-dfm-poc --rm -it -v "$REPO_ROOT/workspace":/app/workspace -p 8003:8003 -p 8002:8002 earth2-blueprint-app:latest
#-u "$(id -u):$(id -g)"

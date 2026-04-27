#!/bin/bash
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Build Earth-2 federation wheels
cd "$REPO_ROOT/earth-2-federation"
bash scripts/build-wheel.sh

# Build Earth-2 Command Center Kit app
cd "$REPO_ROOT/earth-2-command-center"
./build.sh --release

# Set up notebook environment
cd "$REPO_ROOT"
python3 -m venv .venv-notebook
source .venv-notebook/bin/activate
pip install -r notebook_requirements.txt
deactivate

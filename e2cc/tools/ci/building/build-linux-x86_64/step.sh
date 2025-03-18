#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(dirname "${BASH_SOURCE}")"
"$SCRIPT_DIR/../../../../repo.sh" ci build

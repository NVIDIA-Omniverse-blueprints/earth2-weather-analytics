#!/bin/bash
cd /workspace/src
poetry install --no-interaction --no-ansi --with dev --with core
exec "$@"

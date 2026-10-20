#!/usr/bin/env bash
set -euo pipefail

exec docker compose -f ./compose.yaml -f compose.dev.yaml "$@"

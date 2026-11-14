#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec docker-compose -p langfuse --env-file docker/langfuse.env \
  -f langfuse-server/docker-compose.yml -f docker/langfuse.override.yml "$@"

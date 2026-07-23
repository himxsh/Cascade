#!/usr/bin/env bash
set -euo pipefail

GMS_URL="${DATAHUB_GMS_URL:-http://localhost:8080}"

if curl -sf "${GMS_URL}/health" > /dev/null 2>&1; then
    echo "DataHub GMS is healthy at ${GMS_URL}"
    exit 0
else
    echo "DataHub GMS is not reachable at ${GMS_URL}"
    exit 1
fi

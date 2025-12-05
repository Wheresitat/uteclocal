#!/usr/bin/env bash
set -euo pipefail

# Simple curl-based smoke test helper for the gateway endpoints.
# Configure HOST to point at the running gateway (default http://localhost:8000)
# and optionally set DEVICE_ID to run status/lock/unlock calls.
# Example:
#   HOST=http://192.168.1.40:8000 DEVICE_ID=7C:DF:A1:68:3E:6A ./scripts/curl-smoke.sh

HOST=${HOST:-http://localhost:8000}
DEVICE_ID=${DEVICE_ID:-}
HEADER_JSON=("-H" "Content-Type: application/json")

call() {
  echo "> $*"
  # shellcheck disable=SC2086
  eval "$@"
  echo
}

echo "Checking gateway health at ${HOST}/health ..."
call "curl -sS --fail-with-body ${HOST}/health"

echo """Hit /api/devices to verify discovery (requires valid OAuth token or key/secret configured).
Set SKIP_DEVICES=1 to bypass this call."""
if [[ "${SKIP_DEVICES:-0}" != "1" ]]; then
  call "curl -sS --fail-with-body ${HOST}/api/devices"
else
  echo "Skipping /api/devices as requested via SKIP_DEVICES=1"
fi

if [[ -n "${DEVICE_ID}" ]]; then
  echo "Querying status for ${DEVICE_ID} ..."
  call "curl -sS --fail-with-body -X POST ${HOST}/api/status ${HEADER_JSON[*]} -d '{"id":"'"${DEVICE_ID}"'"}'"

  echo "Sending lock action for ${DEVICE_ID} ..."
  call "curl -sS --fail-with-body -X POST ${HOST}/api/lock ${HEADER_JSON[*]} -d '{"id":"'"${DEVICE_ID}"'"}'"

  echo "Sending unlock action for ${DEVICE_ID} ..."
  call "curl -sS --fail-with-body -X POST ${HOST}/api/unlock ${HEADER_JSON[*]} -d '{"id":"'"${DEVICE_ID}"'"}'"
else
  echo "DEVICE_ID not set; skipping status and control calls. Set DEVICE_ID (MAC) to exercise them."
fi

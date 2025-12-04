#!/usr/bin/env bash
set -euo pipefail

# Simple helper to build the gateway image from the repo root with validation.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f Dockerfile ]]; then
  echo "Dockerfile not found. Make sure you cloned the full repo and are running from $PROJECT_ROOT" >&2
  exit 1
fi

if [[ ! -d gateway ]]; then
  echo "gateway/ directory is missing. Please re-clone the repo (git clone https://github.com/Wheresitat/uteclocal.git)." >&2
  exit 1
fi

tag=${1:-uteclocal-gateway}

echo "Building Docker image '$tag' from $PROJECT_ROOT"
docker build -t "$tag" -f Dockerfile .

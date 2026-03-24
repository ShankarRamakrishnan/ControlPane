#!/usr/bin/env bash
# Run the gateway locally from the repo root.
# Both `gateway` and `tools` must be importable, which requires the working
# directory to be the repo root (not gateway/).
set -euo pipefail

cd "$(dirname "$0")"

export TOOLS_DIR="${TOOLS_DIR:-$(pwd)/tools}"
export MANIFESTS_DIR="${MANIFESTS_DIR:-$(pwd)/manifests}"

exec uvicorn gateway.main:app --host 0.0.0.0 --port 8000 --reload

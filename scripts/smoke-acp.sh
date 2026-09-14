#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec .local/runtime-venv/bin/python scripts/smoke-acp.py

#!/usr/bin/env bash
# Repository-local dependencies only. Stops on any download/install failure.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
[[ "$(uname -sm)" == "Linux x86_64" ]] || {
    echo "This spike setup targets Linux x86_64 only." >&2
    exit 1
}
python3 -c 'import sys; assert sys.version_info[:2] == (3, 14), "Expected installed Python 3.14; do not replace host Python"'
mkdir -p .local/bin .local/downloads .local/uv-cache
export UV_CACHE_DIR="$PWD/.local/uv-cache"
export UV_PYTHON_DOWNLOADS=never
export UV_NO_MANAGED_PYTHON=1
export UV_NO_CONFIG=1

# Extract just the binary; no installer, shell profile edits, or system writes.
if [[ ! -x .local/bin/uv ]]; then
    curl --fail --location --connect-timeout 10 --max-time 180 \
        https://github.com/astral-sh/uv/releases/download/0.12.13/uv-x86_64-unknown-linux-gnu.tar.gz \
        --output .local/downloads/uv.tar.gz
    tar -xzf .local/downloads/uv.tar.gz --directory .local/bin \
        --strip-components=1 uv-x86_64-unknown-linux-gnu/uv
fi
python3 -m venv --without-pip .local/runtime-venv
.local/bin/uv pip install --python .local/runtime-venv/bin/python \
    --only-binary=:all: -r runtime/requirements.txt
# Verify the actual SDK/native extension and ASGI app before installing Restate.
.local/runtime-venv/bin/python -c 'import restate; from runtime.app import app; print("SDK/app import OK")'
.local/bin/uv pip freeze --python .local/runtime-venv/bin/python > .local/runtime-resolved.txt

if [[ ! -x .local/bin/restate-server ]]; then
    curl --fail --location --connect-timeout 10 --max-time 180 \
        https://github.com/restatedev/restate/releases/download/v1.7.9/restate-server-x86_64-unknown-linux-musl.tar.xz \
        --output .local/downloads/restate-server.tar.xz
    tar -xJf .local/downloads/restate-server.tar.xz --directory .local/bin \
        --strip-components=1 restate-server-x86_64-unknown-linux-musl/restate-server
fi
.local/bin/restate-server --version

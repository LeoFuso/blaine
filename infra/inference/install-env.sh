#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
inference_env="$HOME/.local/share/blaine/inference/envs/vllm-c3b484463"
if [[ ! -x "$inference_env/bin/python" ]]; then
  uv venv --python 3.13.15 "$inference_env"
fi
uv pip sync --python "$inference_env/bin/python" requirements-existing.lock \
  --extra-index-url https://wheels.vllm.ai/c3b48446349569512749db7f6e2164aa8a33437d \
  --extra-index-url https://download.pytorch.org/whl/cu132 \
  --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match
python3 prepare-cuda.py candidate.json

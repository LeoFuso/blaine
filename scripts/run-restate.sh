#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
# Do not inherit host Restate overrides (especially listeners/data directories).
while IFS= read -r name; do
    unset "$name"
done < <(compgen -v RESTATE_ || true)
exec .local/bin/restate-server --config-file runtime/restate.toml "$@"

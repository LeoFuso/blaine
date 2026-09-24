#!/usr/bin/env bash
# Explicit file allowlist: never package .local host keys/configuration/node state.
set -euo pipefail
root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
source_dir="$root/.local/client-delivery/bin"
out="$root/.local/e0c-direct/distribution"
mkdir -p "$out"
for target in darwin-arm64 linux-amd64; do
  stage="$out/blaine-e0c-$target"
  mkdir -p "$stage"
  cp "$source_dir/blaine-$target" "$stage/"
  cp "$root/experiments/personal-agent-hub/e0c-direct/accept.sh" "$stage/"
  cp "$root/experiments/personal-agent-hub/e0c-direct/OPERATOR.md" "$stage/"
  (cd "$stage" && sha256sum "blaine-$target" accept.sh OPERATOR.md > checksums.txt)
  python3 - "$out" "$target" <<'PACK'
from pathlib import Path
import sys, zipfile
out, target = Path(sys.argv[1]), sys.argv[2]
name = 'blaine-e0c-' + target
with zipfile.ZipFile(out / (name + '.zip'), 'w', zipfile.ZIP_DEFLATED) as archive:
    for filename in ['blaine-' + target, 'accept.sh', 'OPERATOR.md', 'checksums.txt']:
        path = out / name / filename
        assert path.is_file() and not path.is_symlink()
        archive.write(path, name + '/' + filename)
PACK
done
(cd "$out" && sha256sum ./*.zip > downloads.sha256)

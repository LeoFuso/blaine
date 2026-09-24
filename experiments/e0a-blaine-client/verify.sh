#!/usr/bin/env bash
# Run from any cwd with Go 1.27.1 available; no downloads/live dependencies.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
: "${BLAINE_GO:=go}"
export BLAINE_GO
export GOTOOLCHAIN=local GOPROXY=off
export GOCACHE="${GOCACHE:-$PWD/.local/e0a-go-cache}"
export GOPATH="${GOPATH:-$PWD/.local/e0a-go-path}"
if [[ -z "${BLAINE_COMMIT:-}" ]]; then
  BLAINE_COMMIT="$(git rev-parse HEAD)"
  if [[ -n "$(git status --porcelain -- client)" ]]; then BLAINE_COMMIT+="-dirty"; fi
fi
export BLAINE_COMMIT
out=experiments/e0a-blaine-client
"$BLAINE_GO" -C client test -count=1 -v ./... > "$out/tests.txt"
"$BLAINE_GO" -C client test -race -count=1 ./... > "$out/race.txt"
"$BLAINE_GO" -C client vet ./...
echo 'PASS: go vet ./...' > "$out/static.txt"
client/build.sh > "$out/build.txt"
client/build.sh ../.local/e0a-rebuild >> "$out/build.txt"
python3 "$out/accept.py" .local/e0a-artifacts/blaine-linux-amd64 > "$out/live.json"
python3 - <<'PY'
import hashlib, json, os, subprocess
from pathlib import Path
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
artifacts = []
for path in sorted(Path('.local/e0a-artifacts').glob('blaine-*')):
    assert sha(path) == sha(Path('.local/e0a-rebuild') / path.name), 'rebuild mismatch'
    artifacts.append({'name': path.name, 'bytes': path.stat().st_size, 'sha256': sha(path),
                      'format': subprocess.check_output(['file', '-b', str(path)], text=True).strip(),
                      'repeat_build_identical': True})
program_headers = subprocess.check_output(['readelf', '-l', '.local/e0a-artifacts/blaine-linux-amd64'], text=True)
assert 'INTERP' not in program_headers, 'Linux binary needs dynamic interpreter'
source = {str(p): sha(p) for p in sorted(Path('client').rglob('*')) if p.is_file()}
result = {'toolchain': subprocess.check_output([os.environ['BLAINE_GO'], 'version'], text=True).strip(),
          'build_commit': os.environ['BLAINE_COMMIT'], 'linux_amd64_has_no_dynamic_interpreter': True,
          'artifacts': artifacts, 'client_source_sha256': source,
          'runtime_proven': ['linux/amd64'], 'build_only': ['linux/arm64', 'darwin/amd64', 'darwin/arm64'],
          'wsl2_runtime_proven': False}
Path('experiments/e0a-blaine-client/builds.json').write_text(json.dumps(result, indent=2) + '\n')
PY
python3 "$out/check_docs.py" > "$out/docs.txt"
git diff --check
echo 'PASS: tests, race, vet, reproducible builds, live acceptance, documentation, diff'

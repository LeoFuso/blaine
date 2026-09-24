#!/usr/bin/env bash
# Offline verification only. Live acceptance is a separate read-only invocation.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.."
: "${BLAINE_GO:=go}"
export BLAINE_GO
export GOTOOLCHAIN=local GOPROXY=off
export GOCACHE="${GOCACHE:-$PWD/.local/e0b-go-cache}"
export GOPATH="${GOPATH:-$PWD/.local/e0b-go-path}"
if [[ -z "${BLAINE_COMMIT:-}" ]]; then
 BLAINE_COMMIT="$(git rev-parse HEAD)"
 if [[ -n "$(git status --porcelain -- client)" ]]; then BLAINE_COMMIT+="-dirty"; fi
fi
export BLAINE_COMMIT
export BLAINE_VERSION=0.1.0-e0b
out=experiments/e0b-tailscale-onboarding
"$BLAINE_GO" -C client test -count=1 -v ./... > "$out/tests.txt"
"$BLAINE_GO" -C client test -race -count=1 ./... > "$out/race.txt"
"$BLAINE_GO" -C client vet ./...
echo 'PASS: go vet ./...' > "$out/static.txt"
client/build.sh ../.local/e0b-artifacts > "$out/build.txt"
client/build.sh ../.local/e0b-rebuild >> "$out/build.txt"
python3 "$out/accept_offline.py" .local/e0b-artifacts/blaine-linux-amd64 > "$out/offline.json"
python3 - <<'PY'
import hashlib,json,os,subprocess
from pathlib import Path
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[]
for path in sorted(Path('.local/e0b-artifacts').glob('blaine-*')):
 assert sha(path)==sha(Path('.local/e0b-rebuild')/path.name)
 artifacts.append({'name':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'format':subprocess.check_output(['file','-b',str(path)],text=True).strip(),'repeat_build_identical':True})
assert 'INTERP' not in subprocess.check_output(['readelf','-l','.local/e0b-artifacts/blaine-linux-amd64'],text=True)
result={'toolchain':subprocess.check_output([os.environ['BLAINE_GO'],'version'],text=True).strip(),'build_commit':os.environ['BLAINE_COMMIT'],'client_version':os.environ['BLAINE_VERSION'],'linux_amd64_has_no_dynamic_interpreter':True,'cgo_enabled':False,'artifacts':artifacts,'client_source_sha256':{str(p):sha(p) for p in sorted(Path('client').rglob('*')) if p.is_file()},'build_only':['linux/arm64','darwin/amd64','darwin/arm64'],'wsl2_runtime_proven':False}
Path('experiments/e0b-tailscale-onboarding/builds.json').write_text(json.dumps(result,indent=2)+'\n')
PY
git diff --check
echo 'PASS: offline tests, race, vet, reproducible standalone builds and ACP regression'

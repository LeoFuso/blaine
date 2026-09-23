#!/usr/bin/env bash
# Offline E0.C verification; no live Tailscale, SSH, runtime or model calls.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.."
: "${BLAINE_GO:=go}"
export BLAINE_GO GOTOOLCHAIN=local GOPROXY=off
export GOCACHE="${GOCACHE:-$PWD/.local/e0c-go-cache}"
export GOPATH="${GOPATH:-$PWD/.local/e0c-go-path}"
export BLAINE_VERSION=0.1.0-e0c
export BLAINE_COMMIT="$(git rev-parse HEAD)-dirty"
out=experiments/personal-agent-hub/e0c
"$BLAINE_GO" -C client test -count=1 -v ./... > "$out/tests.txt"
"$BLAINE_GO" -C client test -race -count=1 ./... > "$out/race.txt"
"$BLAINE_GO" -C client vet ./...
echo 'PASS: go vet ./...' > "$out/static.txt"
python3 -m unittest tests.test_host_connection -v > "$out/host-tests.txt" 2>&1
client/build.sh ../.local/e0c-artifacts > "$out/build.txt"
client/build.sh ../.local/e0c-rebuild >> "$out/build.txt"
python3 experiments/e0b-tailscale-onboarding/accept_offline.py .local/e0c-artifacts/blaine-linux-amd64 > "$out/offline.json"
python3 - <<'PY'
import hashlib,json,os,subprocess
from pathlib import Path
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
artifacts=[]
for path in sorted(Path('.local/e0c-artifacts').glob('blaine-*')):
 assert sha(path)==sha(Path('.local/e0c-rebuild')/path.name)
 artifacts.append({'name':path.name,'bytes':path.stat().st_size,'sha256':sha(path),'format':subprocess.check_output(['file','-b',str(path)],text=True).strip(),'repeat_build_identical':True})
assert 'INTERP' not in subprocess.check_output(['readelf','-l','.local/e0c-artifacts/blaine-linux-amd64'],text=True)
sources=[p for p in Path('client').rglob('*') if p.is_file()]+[Path('runtime/host_connection.py')]
result={'toolchain':subprocess.check_output([os.environ['BLAINE_GO'],'version'],text=True).strip(),'build_commit':os.environ['BLAINE_COMMIT'],'client_version':os.environ['BLAINE_VERSION'],'linux_amd64_has_no_dynamic_interpreter':True,'artifacts':artifacts,'source_sha256':{str(p):sha(p) for p in sorted(sources)},'build_only':['linux/arm64','darwin/amd64','darwin/arm64'],'wsl2_runtime_proven':False}
Path('experiments/personal-agent-hub/e0c/builds.json').write_text(json.dumps(result,indent=2)+'\n')
PY
git diff --check
echo 'PASS: E0.C offline tests, race, vet, host boundary, four repeat builds, E0.A/B standalone regression'

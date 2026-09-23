#!/usr/bin/env bash
# Shared repository-owned CI/release validation; no live services or credentials.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
: "${BLAINE_GO:=go}"
: "${BLAINE_VERSION:?Set the client version}"
: "${BLAINE_COMMIT:?Set the exact source commit (local validation may append -dirty)}"
export BLAINE_GO BLAINE_VERSION BLAINE_COMMIT GOTOOLCHAIN=local GOPROXY=off
root="$PWD"
out="$root/.local/client-delivery"
mkdir -p "$out/validation"
expected="go$(cat client/.go-version)"
[[ "$("$BLAINE_GO" env GOVERSION)" == "$expected" ]] || { echo "Expected $expected" >&2; exit 1; }
if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
  [[ "$BLAINE_COMMIT" == "$(git rev-parse HEAD)" ]]
  git diff --exit-code HEAD
fi
formatter="$("$BLAINE_GO" env GOROOT)/bin/gofmt"
unformatted="$("$formatter" -l client)"
[[ -z "$unformatted" ]] || { printf 'Run gofmt on:\n%s\n' "$unformatted" >&2; exit 1; }
echo 'PASS: gofmt' > "$out/validation/format.txt"
"$BLAINE_GO" -C client test -count=1 -v ./... | tee "$out/validation/tests.txt"
"$BLAINE_GO" -C client test -race -count=1 ./... | tee "$out/validation/race.txt"
"$BLAINE_GO" -C client vet ./...
echo 'PASS: go vet' > "$out/validation/vet.txt"
sh -n client/install-jetbrains-agent.sh
python3 -m unittest discover -s client/tests -v 2>&1 | tee "$out/validation/installer-tests.txt"
python3 -m unittest tests.test_host_connection tests.test_direct_readiness -v 2>&1 | tee "$out/validation/host-tests.txt"
client/build.sh "$out/bin" | tee "$out/validation/build.txt"
client/build.sh "$out/rebuild" >> "$out/validation/build.txt"
python3 experiments/e0b-tailscale-onboarding/accept_offline.py "$out/bin/blaine-linux-amd64" --direct > "$out/validation/offline.json"
python3 client/verify-build.py "$out"
git diff --check

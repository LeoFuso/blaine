#!/usr/bin/env bash
# Fixed three-run measurement, never retry-until-success or a product launcher.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "$(uname -s)/$(uname -m)" in
 Darwin/arm64) binary=blaine-spike-darwin-arm64 ;;
 Darwin/x86_64) binary=blaine-spike-darwin-amd64 ;;
 Linux/x86_64) binary=blaine-spike-linux-amd64 ;;
 Linux/aarch64) binary=blaine-spike-linux-arm64 ;;
 *) echo 'STOP: unsupported spike platform' >&2; exit 2 ;;
esac
if command -v shasum >/dev/null; then
 shasum -a 256 -c checksums.txt
else
 sha256sum -c checksums.txt
fi
chmod u+x "$binary"
reports=$(mktemp -d ./reports-peer-observation-XXXXXX)
echo 'Three independent observations; keep system Tailscale in the agreed test state.'
echo 'Each observes embedded peer visibility for 20 seconds, then tests name/IP once.'
for run in 1 2 3; do
 echo "Observation $run/3"
 "./$binary" tsnet --diagnose --observe-peers | tee "$reports/run-$run.json"
done
echo "Send only the three JSON files in $reports; never send private node state."

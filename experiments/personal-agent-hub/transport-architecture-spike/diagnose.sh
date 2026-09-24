#!/usr/bin/env bash
# Isolated diagnostic fixture; does not change system networking or node state.
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
mkdir -p reports
echo 'Diagnostic only; keep system Tailscale in the agreed test state.'
echo 'Never share the private state directory or authentication URL.'
"./$binary" tsnet --diagnose | tee reports/connectivity-diagnostic.json

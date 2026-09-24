#!/usr/bin/env bash
# Disposable experiment, not a Blaine installer. No system Tailscale dependency.
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
echo 'Experimental application node: browser login may be required. No auth keys needed.'
echo 'Do not share the private state directory or any authentication URL.'
mkdir -p reports
"./$binary" tsnet > reports/first.json
cat reports/first.json
# Simulates a changed executable cache location, not an actual version upgrade.
mkdir -p relocated-bin
cp "$binary" relocated-bin/probe
chmod u+x relocated-bin/probe
./relocated-bin/probe tsnet > reports/relocated-repeat.json
cat reports/relocated-repeat.json
echo 'Send only reports/first.json and reports/relocated-repeat.json.'
echo 'PASS here covers this fixture; reboot, real upgrade, revocation and IDE remain separate gates.'

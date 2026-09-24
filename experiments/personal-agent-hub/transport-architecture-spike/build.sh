#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.."
root="$PWD"
: "${BLAINE_GO:=/tmp/blaine-e0a-toolchain/go/bin/go}"
export GOTOOLCHAIN=local GOCACHE="${GOCACHE:-/tmp/blaine-go-cache}" GOPATH="${GOPATH:-/tmp/blaine-go-path}"
out="${BLAINE_SPIKE_OUT:-$root/.local/transport-architecture-spike}"
mkdir -p "$out"
cd "$root/experiments/personal-agent-hub/transport-architecture-spike/probe"
source_hash=$(cat *.go go.mod go.sum | sha256sum | cut -d' ' -f1)
for target in darwin/arm64 linux/amd64 darwin/amd64 linux/arm64; do
  GOOS=${target%/*} GOARCH=${target#*/} CGO_ENABLED=0 "$BLAINE_GO" build -trimpath -buildvcs=false -ldflags="-s -w -X main.spikeCommit=source-$source_hash" -o "$out/blaine-spike-${target/\//-}" .
done
cd "$out"
sha256sum blaine-spike-* > checksums.txt

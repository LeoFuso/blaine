#!/usr/bin/env bash
# Reproducible standalone artifacts; no downloads, installers or host mutation.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
: "${BLAINE_VERSION:=0.1.0-e0b}"
: "${BLAINE_COMMIT:?Set BLAINE_COMMIT to the source commit (append -dirty for local edits)}"
: "${BLAINE_GO:=go}"
if [[ ! "$BLAINE_VERSION" =~ ^[a-zA-Z0-9.+-]+$ || ! "$BLAINE_COMMIT" =~ ^[a-zA-Z0-9.+-]+$ ]]; then
  echo 'Invalid build metadata' >&2
  exit 64
fi
out="${1:-../.local/e0b-artifacts}"
mkdir -p -- "$out"
export GOTOOLCHAIN=local GOPROXY=off CGO_ENABLED=0
for target in linux/amd64 darwin/amd64 darwin/arm64 linux/arm64; do
  GOOS="${target%/*}" GOARCH="${target#*/}" "$BLAINE_GO" build \
    -trimpath -buildvcs=false \
    -ldflags "-buildid= -s -w -X blaine.local/client/internal/buildinfo.Version=$BLAINE_VERSION -X blaine.local/client/internal/buildinfo.Commit=$BLAINE_COMMIT" \
    -o "$out/blaine-${target//\//-}" ./cmd/blaine
  echo "BUILD $target"
done

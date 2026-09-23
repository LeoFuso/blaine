#!/bin/sh
# Development bootstrap only. All ACP JSON semantics belong to the verified Go client.
set -eu

main() {
  release=v0.1.0-alpha.3
  mode=install
  case $# in
    0) ;;
    1) case $1 in --check) mode=check ;; *) echo 'usage: install-jetbrains-agent.sh [--check]' >&2; return 64 ;; esac ;;
    *) echo 'usage: install-jetbrains-agent.sh [--check]' >&2; return 64 ;;
  esac
  case $(uname -s) in Darwin) os=darwin ;; Linux) os=linux ;; *) echo 'Unsupported OS; use macOS or Linux/WSL2' >&2; return 1 ;; esac
  case $(uname -m) in arm64|aarch64) arch=arm64 ;; x86_64|amd64) arch=amd64 ;; *) echo 'Unsupported architecture' >&2; return 1 ;; esac
  asset=blaine-$os-$arch
  case ${HOME:-} in /*) ;; *) echo 'Absolute HOME required' >&2; return 1 ;; esac
  bin_dir=$HOME/.local/bin
  binary=$bin_dir/blaine
  printf 'platform: %s/%s\nrelease: %s\nasset: %s\ninstalled path: %s\n' "$os" "$arch" "$release" "$asset" "$binary"
  # Do not follow user-level symlinks to unexpected installation targets.
  path=$binary
  while [ "$path" != / ]; do
    if [ -L "$path" ]; then echo "Symlink installation path refused: $path" >&2; return 1; fi
    path=${path%/*}; [ -n "$path" ] || path=/
  done
  if [ -e "$binary" ] && [ ! -f "$binary" ]; then echo 'Expected a regular installed executable' >&2; return 1; fi
  if [ "$mode" = check ]; then
    if [ ! -x "$binary" ]; then echo 'installed: absent'; return 1; fi
    "$binary" version
    "$binary" integration jetbrains check
    return
  fi
  if [ "$(id -u)" = 0 ]; then echo 'Run as the workstation user, without sudo' >&2; return 1; fi
  command -v curl >/dev/null 2>&1 || { echo 'curl required' >&2; return 1; }
  umask 077
  stage=$(mktemp -d "${TMPDIR:-/tmp}/blaine-install.XXXXXX")
  pending=
  trap 'rm -rf "$stage"; if [ -n "$pending" ]; then rm -f "$pending"; fi' 0
  trap 'exit 130' INT
  trap 'exit 143' TERM HUP
  base=https://github.com/LeoFuso/blaine/releases/download/$release
  for file in "$asset" checksums.txt; do
    curl -fsSL --proto '=https' --proto-redir '=https' --connect-timeout 15 --max-time 300 \
      --max-filesize 268435456 "$base/$file" -o "$stage/$file"
  done
  expected= count=0
  while read -r hash file extra; do
    file=${file#\*}
    if [ "$file" = "$asset" ]; then
      [ -z "$extra" ] || { echo 'Malformed checksum entry' >&2; return 1; }
      case $hash in *[!0-9a-f]*|'') echo 'Invalid SHA-256 value' >&2; return 1 ;; esac
      [ "${#hash}" = 64 ] || { echo 'Invalid SHA-256 length' >&2; return 1; }
      count=$((count + 1)); expected=$hash
    fi
  done < "$stage/checksums.txt"
  [ "$count" = 1 ] || { echo 'Expected exactly one checksum for selected asset' >&2; return 1; }
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$stage/$asset" > "$stage/digest"
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$stage/$asset" > "$stage/digest"
  else
    echo 'SHA-256 tool required (sha256sum or shasum)' >&2; return 1
  fi
  read -r actual rest < "$stage/digest"
  [ "$actual" = "$expected" ] || { echo 'Checksum mismatch; binary not executed or installed' >&2; return 1; }
  printf 'checksum: verified (%s)\n' "$actual"
  chmod 700 "$stage/$asset"
  metadata=$("$stage/$asset" version)
  case $metadata in "blaine ${release#v} protocol=1 commit="*" platform=$os/$arch") ;; *) echo 'Release/platform metadata mismatch' >&2; return 1 ;; esac
  # Validate existing ACP configuration before replacing an installed executable.
  "$stage/$asset" integration jetbrains check >/dev/null
  mkdir -p "$bin_dir"
  pending=$(mktemp "$bin_dir/.blaine-install.XXXXXX")
  cp "$stage/$asset" "$pending"
  chmod 755 "$pending"
  mv -f "$pending" "$binary"
  pending=
  "$binary" integration jetbrains install
  "$binary" version
  printf 'installed: %s\n' "$binary"
  # The IDE uses an absolute executable; no profile edits or PATH surgery required.
}
main "$@"

# Install the Blaine workstation client alpha

> The published `v0.1.0-alpha.1` uses the previous E0.C transport candidate. The
> selected embedded-tsnet migration is not published yet; its controlled local
> candidate procedure is [here](../experiments/personal-agent-hub/e0c-direct/OPERATOR.md).
> Do not treat the old release as evidence for the new transport.


The first version is **v0.1.0-alpha.1**. This is an experimental prerelease, not
stable E0/client acceptance. A binary requires no Go installation, repository
checkout or copy from the Blaine host. Release availability and actual CI proof
are recorded in the [delivery report](../experiments/personal-agent-hub/e0c/delivery.md).

Download from the public [GitHub Releases](https://github.com/LeoFuso/blaine/releases)
page. Select the exact version; prereleases are deliberately not marked latest.
Each version has these raw assets and one `checksums.txt` covering all four:

| Workstation | Asset |
| --- | --- |
| Apple Silicon macOS | `blaine-darwin-arm64` |
| Intel macOS | `blaine-darwin-amd64` |
| Linux amd64 / Windows + WSL2 amd64 | `blaine-linux-amd64` |
| Linux arm64 / WSL2 arm64 | `blaine-linux-arm64` |

Run the following manual commands in a shell on the workstation. On Windows run
inside the selected WSL2 distribution, not PowerShell; there is no native Windows
client. These commands verify only the downloaded platform's entry in the
four-binary manifest. `test` must succeed before `install` runs.

## macOS arm64

```bash
(
  set -eu
  work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT; cd "$work"
  base=https://github.com/LeoFuso/blaine/releases/download/v0.1.0-alpha.1
  curl -fL --proto '=https' -O "$base/blaine-darwin-arm64"
  curl -fL --proto '=https' -O "$base/checksums.txt"
  test "$(shasum -a 256 blaine-darwin-arm64 | awk '{print $1}')" = "$(awk '$2=="blaine-darwin-arm64" {print $1}' checksums.txt)"
  mkdir -p "$HOME/.local/bin"
  install -m 755 blaine-darwin-arm64 "$HOME/.local/bin/blaine"
  "$HOME/.local/bin/blaine" version
)
```

## macOS amd64

```bash
(
  set -eu
  work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT; cd "$work"
  base=https://github.com/LeoFuso/blaine/releases/download/v0.1.0-alpha.1
  curl -fL --proto '=https' -O "$base/blaine-darwin-amd64"
  curl -fL --proto '=https' -O "$base/checksums.txt"
  test "$(shasum -a 256 blaine-darwin-amd64 | awk '{print $1}')" = "$(awk '$2=="blaine-darwin-amd64" {print $1}' checksums.txt)"
  mkdir -p "$HOME/.local/bin"
  install -m 755 blaine-darwin-amd64 "$HOME/.local/bin/blaine"
  "$HOME/.local/bin/blaine" version
)
```

## Linux / WSL2 amd64

```bash
(
  set -eu
  work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT; cd "$work"
  base=https://github.com/LeoFuso/blaine/releases/download/v0.1.0-alpha.1
  curl -fL --proto '=https' -O "$base/blaine-linux-amd64"
  curl -fL --proto '=https' -O "$base/checksums.txt"
  test "$(sha256sum blaine-linux-amd64 | awk '{print $1}')" = "$(awk '$2=="blaine-linux-amd64" {print $1}' checksums.txt)"
  mkdir -p "$HOME/.local/bin"
  install -m 755 blaine-linux-amd64 "$HOME/.local/bin/blaine"
  "$HOME/.local/bin/blaine" version
)
```

For Linux/WSL arm64 substitute `blaine-linux-arm64` in the Linux block.
After installation, in any supported shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
blaine version --json
blaine doctor
blaine connect --host blaine
```

Doctor/connect are expected to report unready/pending gates in this alpha; they
are not evidence of E0 PASS. Tailscale stays external infrastructure. macOS and
Windows+WSL2 live peer identity, guest routing, handshake and remote ACP acceptance
are still required. The current WSL transport intentionally refuses to claim a
verified route. No production host peer resolver/dispatcher is enabled.

Darwin cross-builds are not signed/notarized and do not establish macOS runtime
support. If OS trust policy blocks launch, retain that observation for acceptance;
do not disable system security policy. The manifest supplies download integrity,
not a signing identity or attested build provenance.

## Branch and commit artifacts

[Client CI](https://github.com/LeoFuso/blaine/actions/workflows/client-ci.yml)
uploads separate artifacts named for each binary and `blaine-checksums` on relevant
branch/PR builds. Pick a successful run with the intended exact commit, download
its platform artifact and checksum artifact from the same run, unzip both into
a directory, then use the same checksum comparison and `install` command above.
Actions downloads may require a GitHub login; public Release downloads do not.
Archive extraction may not preserve executable permissions; `install -m 755` sets
them explicitly. Branch versions are `0.1.0-dev+<12-character-commit>` and the
embedded `build_commit` remains the full exact built commit (PR runs build their
merge commit). Do not mix artifacts from different runs.

## Release semantics and follow-ups

- CI: `.github/workflows/client-ci.yml`; shared validation/build:
  `.github/workflows/client-build.yml`; tag publication:
  `.github/workflows/client-release.yml`.
- Pin: `client/.go-version` currently **1.27.1**. Validation requires that exact
  toolchain. Official GitHub actions are pinned by immutable commit SHA.
- Only explicit `v0.x.y-alpha.N` tags are supported initially. `v` is removed from
  the embedded client version; protocol remains independently versioned at 1.
  Releases are prereleases and never marked latest. Tags/releases are not moved
  or overwritten automatically. Stable/beta semantics require a later deliberate
  change, not an accidental non-alpha tag.
- Compilation needs no secret. CI has `contents: read`; only the publication job
  has `contents: write`, using GitHub's ephemeral token. Nothing is merged by CI.
- GitHub Actions supplies artifact archive digests; the release supplies SHA-256
  of the actual binaries. Neither is being represented as a native attestation.
  GitHub-native provenance/attestation is deferred hardening; adding its OIDC and
  attestation permissions should be reviewed separately.
- **Changie/changelog automation is explicitly deferred** until this release
  workflow and version semantics are proven. No changelog generator, self-updater
  or final installer is included. This is supporting delivery for E0.C, not E0.F
  product acceptance or implementation of E0.D+.

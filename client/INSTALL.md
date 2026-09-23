# Install the Blaine workstation client alpha

> The published `v0.1.0-alpha.1` uses the previous E0.C transport candidate. The
> selected embedded-tsnet migration is not published yet; its controlled local
> candidate procedure is [here](../experiments/personal-agent-hub/e0c-direct/OPERATOR.md).
> Do not treat the old release as evidence for the new transport.

## Development JetBrains bootstrap

[`install-jetbrains-agent.sh`](install-jetbrains-agent.sh) is a self-contained,
user-local development installer. It requires **Python 3.8+** for structural JSON
handling and **curl** for public release downloads. It does not install runtimes,
Tailscale, SSH configuration or credentials. No sudo is needed or accepted.
ACP Registry provisioning remains the product direction.

From a checkout or a downloaded copy of this script:

```sh
sh ./install-jetbrains-agent.sh
sh ./install-jetbrains-agent.sh --check
```

The default is the explicit published **v0.1.0-alpha.1**, not GitHub's latest
release alias. The installer detects Darwin/Linux and arm64/amd64, downloads the
matching raw binary and `checksums.txt` from `LeoFuso/blaine` GitHub Releases,
requires exactly one matching SHA-256 entry, and verifies staged bytes **before
execution or installation**. It then checks embedded version, platform, protocol
and exact commit metadata and installs to `~/.local/bin/blaine`. An explicit future
published alpha can be selected with `--release v0.x.y-alpha.N`.

**Current E0.C acceptance must use the existing direct candidate**, because the
published alpha still uses SSH. From the previously downloaded, trusted candidate
package directory, run the downloaded installer with:

```sh
sh "$HOME/Downloads/install-jetbrains-agent.sh" --candidate-dir "$PWD"
sh "$HOME/Downloads/install-jetbrains-agent.sh" --candidate-dir "$PWD" --check
```

This explicit alternative verifies that package's binary against its own
`checksums.txt`; it makes no GitHub-release/provenance claim. It reuses the candidate
already exercised on the designated peer. Do not use a manifest supplied by an
untrusted source. The default old-alpha installation refuses to replace an existing
different-version client, preventing accidental rollback of the direct candidate.

The script registers **Blaine** in `~/.jetbrains/acp.json` using the absolute stable
executable path and `args: ["acp"]`; PATH changes are unnecessary for IDE launch.
On WSL it locates the Windows user's profile through Windows interop and updates
the **Windows IDE's** configuration, using `wsl.exe --distribution <current distro>
--exec /home/<user>/.local/bin/blaine acp`. It does not assume that opening a WSL
project makes the IDE itself a Linux process. Missing Windows interop fails closed.
Real WSL IDE interoperability is still pending: the current
[JetBrains documentation](https://www.jetbrains.com/help/ai-assistant/acp.html)
explicitly lists WSL as unsupported, so registration alone cannot establish PASS.

Existing agents, global defaults and extension fields are preserved. An existing
`Blaine` or `Blaine E0.C candidate` entry is updated in place; multiple such entries
fail as ambiguous. Invalid/duplicate-key JSON, unexpected file types and symlinks
fail before modification. A changed existing configuration gets one rolling
`acp.json.blaine-backup` containing its previous exact bytes; that backup can contain
existing agent credentials and must stay private. Repeating an unchanged install
does not rewrite the binary/configuration/backup. Files are replaced atomically;
the binary and configuration are separate replacements, not a two-file transaction.
An interrupted installation can be rerun. Close the IDE configuration editor during
installation; concurrent installer runs are locked and configuration changes during
download are detected. Windows-hosted files ultimately rely on Windows user-profile
ACLs; Unix mode bits alone are not a Windows confidentiality guarantee.

`--check` performs no download, installation, directory creation or config writes.
It reports platform, selected source/asset, installed version/commit/path,
registration presence and whether executable/arguments match. It executes only the
existing local `blaine version --json`, not a handshake or session.

Open AI Chat and select Blaine after installation. For E0.C, turn off **Pass custom
MCP servers** and **Pass IntelliJ MCP server** for Blaine in Agents settings. The
installer disables these defaults only when creating a fresh configuration; it
never changes existing agents' global policy. It neither opens an ACP session nor
performs browser authentication automatically. macOS signing/notarization remains
unproven; no system security settings or quarantine attributes are changed.

Once this script is authorized and published to the repository, the pipe entrypoint
can use a pinned, actually published commit. This is a **template, not a currently
available installer URL** (this local change has not been pushed):

```sh
curl -fsSL https://raw.githubusercontent.com/LeoFuso/blaine/<published-commit>/client/install-jetbrains-agent.sh | sh
```

Until publication is authorized, use the local downloadable script. No release,
registry submission, self-updater or changelog automation is introduced here.

## Manual release installation

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

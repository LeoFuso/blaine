# Install the Blaine workstation client alpha

**v0.1.0-alpha.2** is the first direct-transport prerelease: embedded tsnet plus
Blaine's private application protocol. E0.C remains PARTIAL. The alpha is not a
stable client or proof of real IntelliJ acceptance. **v0.1.0-alpha.1 is historical
SSH-transport evidence and must not be used for current product acceptance.**

## Current development onboarding

On macOS or Linux (including the designated Ubuntu WSL2 environment):

```sh
curl -fsSL https://raw.githubusercontent.com/LeoFuso/blaine/v0.1.0-alpha.3/client/install-jetbrains-agent.sh | sh
```

The current target is **alpha.3**, which fixes the auxiliary `type` field rejected
by alpha.2 during real JetBrains launch. [Alpha.3 delivery evidence](../experiments/personal-agent-hub/e0c-direct/alpha3-delivery.json)
records publication and validation status. The earlier
[alpha.2 evidence](../experiments/personal-agent-hub/e0c-direct/alpha2-delivery.json)
remains historical; installation success did not establish an IDE ACP session. This is development scaffolding. ACP Registry
publication has **not** happened and remains the final distribution direction.

The shell bootstrap requires a POSIX shell, curl, and `sha256sum` (Linux) or
`shasum` (macOS). **It requires no Python, Go, Node, system Tailscale or SSH.**
It detects the platform, downloads the exact alpha.3 asset and public
`checksums.txt`, requires exactly one matching SHA-256 entry, and compares bytes
before executing or installing the binary. No `latest` alias or local candidate
fallback is used. Checksum failure leaves the installed binary unchanged.

| Workstation | Asset |
| --- | --- |
| Apple Silicon Mac | `blaine-darwin-arm64` |
| Intel Mac | `blaine-darwin-amd64` |
| Linux / Ubuntu WSL2 amd64 | `blaine-linux-amd64` |
| Linux arm64 | `blaine-linux-arm64` |

The binary is installed at `~/.local/bin/blaine`. The verified binary first checks
existing JetBrains configuration, then performs registration from its installed
location. The IDE uses the absolute executable path with `args: ["acp"]`; no PATH
or shell-profile editing is required. The installer prints the client version,
exact build commit, checksum, executable path and registration result.

Open IntelliJ **AI Chat** and select **Blaine**. Restart the IDE if it has not
reloaded the configuration. For E0.C, disable **Pass custom MCP servers** and
**Pass IntelliJ MCP server** for Blaine in Agents settings. Existing agents' global
MCP policy is preserved; fresh configuration starts with MCP exposure disabled.
The client advertises no E1/E2 workspace capabilities. Authentication, when needed,
uses the client-owned browser flow; installation does not start tsnet or enroll a
new node. Existing private installation identity remains in its existing state
location across upgrades.

macOS binaries are not signed/notarized. If Gatekeeper blocks launch, report that
separately; the installer does not alter quarantine or disable system security.
Checksums provide download integrity, not signing or build attestation.

## Status and Go-owned JetBrains integration

```sh
curl -fsSL https://raw.githubusercontent.com/LeoFuso/blaine/v0.1.0-alpha.3/client/install-jetbrains-agent.sh | sh -s -- --check
"$HOME/.local/bin/blaine" integration jetbrains check --json
"$HOME/.local/bin/blaine" integration jetbrains install
"$HOME/.local/bin/blaine" version
```

`--check` downloads only the installer script, not a client asset. It executes the
existing local version/status commands without modifying configuration or connecting
to the Hub. The Go `integration jetbrains check` also works without a configuration.
It reports registration presence and whether executable/arguments match.

The Go client owns all `acp.json` semantics: strict structural parsing (including
rejection of duplicate keys), preservation of unrelated agents/extension fields,
an idempotent owned entry, and a single rolling `acp.json.blaine-backup` of the
previous exact valid bytes when modification is required. Existing `Blaine` or
`Blaine E0.C candidate` entries are updated in place; multiple matches are rejected
as ambiguous. Invalid configuration, symlinks and hardlinks fail closed. A backup
may contain other agents' credentials; keep it private. Existing native files are
replaced atomically with user-private permissions. Do not edit the configuration
concurrently; installer writes are locked and changes detected before replacement.

On Linux/macOS the config is `~/.jetbrains/acp.json`. In the **designated topology
of Windows IntelliJ opening an Ubuntu WSL2 project**, Go locates the Windows user's
home with Windows interop and registers `wsl.exe --distribution <current distro>
--exec /home/<user>/.local/bin/blaine acp` in the Windows IDE config. This is process
launch interop, not a dependency on Windows Tailscale or a Linux daemon. Missing
interop fails closed; there is no automatic fallback to a different IDE topology.
Windows profile ACLs govern Windows-hosted files; Unix mode bits alone do not prove
confidentiality there. Real IDE launch must still be tested: current
[JetBrains documentation](https://www.jetbrains.com/help/ai-assistant/acp.html)
lists WSL as unsupported. A successful registration is not evidence of UI support.

The binary and JSON updates are separate atomic replacements, not a two-file
transaction. Rerun after an interrupted installation. No credentials, Hub hostname,
remote Unix account, SSH configuration or Tailscale installation is provisioned by
the installer. Reset/revocation of the embedded identity is a separate explicit
client operation; this installer does not reset it.

## Delivery and validation

The official [GitHub Release](https://github.com/LeoFuso/blaine/releases/tag/v0.1.0-alpha.3)
contains the four raw binaries above and one `checksums.txt`. Existing repository
workflows remain authoritative:

- CI: `.github/workflows/client-ci.yml`.
- Shared validation/four-target build: `.github/workflows/client-build.yml` and
  `client/ci.sh`, including Go tests/race/vet, installer fixtures, host regressions,
  offline client regressions and reproducibility checks.
- Tag publication: `.github/workflows/client-release.yml`; explicit `v0.x.y-alpha.N`
  tags become prereleases, never the stable latest release. Embedded client version
  omits `v`; protocol version remains independently versioned at 1.
- Go is pinned to **1.27.1**. Ordinary CI has read-only permissions; only the release
  publication job has `contents: write`. Compilation requires no secret.
- Actions provides commit-build artifacts with the same binary names and a
  `blaine-checksums` artifact. Public E0 onboarding uses the tagged Release.
- Native signing/notarization and GitHub build attestation remain deferred
  hardening; Actions archive digests are not being represented as attestations.
- Changie/changelog automation remains explicitly deferred. No self-updater,
  native Windows binary, custom JetBrains plugin or E0.D+ implementation is added.

The old manual alpha.1 instructions remain in Git history and the
[historical delivery evidence](../experiments/personal-agent-hub/e0c/delivery.md).
They are not a fallback for a failing direct transport.

# E0.C supporting client delivery

**PASS — GitHub CI, downloadable Actions Artifacts and first public alpha
Release. E0.C itself remains PARTIAL.** Delivery does not establish trusted remote
peer identity, a production host dispatcher or live remote ACP acceptance.

The [request](delivery-request.json) is **unsubmitted**: no durable development
binding was exposed. The user explicitly authorized GitHub Actions/Release delivery,
superseding the original local-only publication restriction for this support work.
No merge was performed. No E0.D+ implementation was added.

## Published source and semantics

- Tag: **`v0.1.0-alpha.1`**.
- Tagged commit: **`ca4a6b2e31d58bc649257700a87efd8a1c326b96`**.
- Embedded version: `0.1.0-alpha.1`; independent protocol: `1`; exact full commit.
- [Public prerelease](https://github.com/LeoFuso/blaine/releases/tag/v0.1.0-alpha.1):
  not a draft, explicitly prerelease, not marked latest. No stable E0/client claim.
- Only explicit `v0.x.y-alpha.N` tags are supported by the initial workflow;
  publication refuses other version semantics. Tags/assets are not silently moved
  or overwritten. No changelog generation is performed.

The repository initially had no local/remote GitHub workflows, tags or releases,
and no conflicting canonical versioning convention. The tag, exact commit,
semantics, workflows, target matrix, assets and checksum/provenance behavior were
reported before publication. The E0.C branch was published without merging it.

GitHub's release API may report `targetCommitish: main` as its default metadata
for an already-existing tag. The annotated Git tag, Actions `headSha`, downloaded
binary metadata and the retained proof all resolve to the exact commit above;
the release did not build `main` or move the tag.

## CI and artifact proof

| Item | Evidence |
| --- | --- |
| CI entrypoint | [client-ci.yml](../../../.github/workflows/client-ci.yml): relevant client/build/workflow/regression paths, branch pushes, PRs and manual dispatch |
| Shared build | [client-build.yml](../../../.github/workflows/client-build.yml), used by both CI and release |
| Toolchain | **Go 1.27.1**, pinned in [client/.go-version](../../../client/.go-version); official actions pinned by full commit SHA |
| Branch Actions result | [Run 35800514062 — SUCCESS](https://github.com/LeoFuso/blaine/actions/runs/35800514062) |
| Actual downloaded artifacts | [delivery-ci-proof.json](delivery-ci-proof.json): artifact IDs, archive digests, all four binary checksum matches and native metadata readback |
| Release workflow | [client-release.yml](../../../.github/workflows/client-release.yml) |
| Tag Actions result | [Run 35800774597 — SUCCESS](https://github.com/LeoFuso/blaine/actions/runs/35800774597) |
| Public asset proof | [delivery-release-proof.json](delivery-release-proof.json): release/asset metadata, all four checksum matches, anonymous HTTPS and isolated Linux installation |

Both workflows ran formatting, Go tests, Linux amd64 race checks, vet, Python host
boundary tests, E0.A/B standalone byte/process regressions and E0.C client tests.
They built all four targets twice and verified identical hashes. Native Linux
metadata checks enforce version, protocol, exact commit and Go version; its binary
has no ELF dynamic interpreter. Workflow syntax was also checked locally with
checksum-verified upstream actionlint 1.7.12. Compilation uses only the Go standard
library and requires no secret.

Branch builds upload separate Actions Artifacts named:

```text
blaine-linux-amd64
blaine-linux-arm64
blaine-darwin-amd64
blaine-darwin-arm64
blaine-checksums
client-validation
```

The first four contain the corresponding raw binary. `blaine-checksums` contains
`checksums.txt`; `client-validation` retains logs, standalone regression evidence
and build metadata. Download the binary and manifest from the same successful run.
Branch versions are `0.1.0-dev+<12-character-commit>`, retaining the full commit in
`build_commit`. PR runs identify their actual merge commit.

## Published assets and checksums

The release contains exactly five assets:

```text
blaine-linux-amd64
blaine-linux-arm64
blaine-darwin-amd64
blaine-darwin-arm64
checksums.txt
```

One SHA-256 manifest covers all four binaries. Every released binary was downloaded
and verified against it. The manifest and Linux amd64 binary were additionally
retrieved anonymously over HTTPS, without GitHub credentials. The Linux artifact
was installed under an isolated home, outside the checkout, and run with an empty
PATH: `version --json` matched alpha/protocol/commit/Go metadata; `doctor` returned
its expected `NOT_READY`/2 without creating configuration or state.

These are public workstation downloads, not host-built/SCP distribution. Exact
manual commands for macOS arm64, macOS amd64 and Linux/WSL amd64 are in the
[installation guide](../../../client/INSTALL.md). Windows+WSL2 uses Linux binaries;
there is no native Windows target.

## Permissions, provenance and deferred work

Ordinary CI and reusable compilation have `contents: read`. Only the release
publication job has `contents: write`, using GitHub's ephemeral token. No custom
secret, OIDC permission or signing credential is needed to compile the client.

Actions archive digests and the binary SHA-256 manifest were verified. These are
integrity evidence, **not native provenance attestations**. GitHub-native
attestation is explicitly deferred hardening; its OIDC/attestation permissions
were not added to the first alpha path. macOS signing/notarization is also not
claimed.

**Changie/changelog automation is explicitly deferred** until the delivery/version
semantics are proven; it remains a small release-engineering follow-up. There is
no self-updater or final installer. Generated binaries, downloaded archives and
compiler artifacts stay under ignored `.local/` or `/tmp`; none were committed.

## Resumed E0.C acceptance and platform limits

[Released-client local observations](delivery-live-linux.json) used the actual
public `v0.1.0-alpha.1` Linux amd64 binary. Read-only connect/doctor and host probes
preserved their fail-closed outcomes, no profile was persisted, and network
identity, addresses, preferences and native SSH trust stayed unchanged. Runtime,
Restate and model reads passed; MIRIX dependency readiness stayed UNKNOWN.

| Platform | Designed | Build-verified | Runtime evidence |
| --- | --- | --- | --- |
| Linux amd64 | Yes | GitHub Actions, repeated builds | Download/install/version/doctor plus local host observations; not second-peer ACP |
| Linux arm64 | Yes | GitHub Actions, repeated builds | Not yet run on arm64 hardware |
| macOS arm64 / amd64 | Yes | Both Darwin Actions assets, repeated builds | Live peer use pending designated Mac and access; no signed/notarized claim |
| Windows + WSL2 | Yes, Linux client | Linux artifacts | Live Windows-owned route/identity/ACP pending designated WSL2 workstation and access |

The user has been asked to designate the macOS and Windows+WSL2 machines and their
access paths. No other tailnet device was repurposed. The Mac will consume its
Darwin Release asset; Windows+WSL2 amd64 will consume the Linux amd64 Release asset.
Neither requires a manual build or file copy from the Blaine host.

**Next work remains the canonical E0.C live identity/host/handshake/framing gates.**
The exact next slice is **E0.D — Registration**, only after E0.C acceptance.
No registration, IntelliJ configuration, remote workspace reads/writes/exec,
coding-task behavior, public gateway/OIDC or plugin work was pulled forward.

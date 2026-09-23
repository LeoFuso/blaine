# E0.C supporting client delivery

Implementation/validation in progress. This is delivery support for E0.C, not a
new milestone or acceptance of the unfinished peer-identity/remote ACP gates.
The [request](delivery-request.json) is unsubmitted: no durable development binding
was available. The user explicitly authorized the GitHub Actions/Release path.

The repository had no `.github` workflows, remote Actions workflows, tags or
releases, and no conflicting versioning convention. Proposed first tag:
`v0.1.0-alpha.1`, embedded version `0.1.0-alpha.1`, protocol 1, exact tagged commit.
It is an alpha prerelease, never a stable/latest release. Publication uses the
E0.C branch without merging it.

CI: `.github/workflows/client-ci.yml`. Shared validation/build:
`.github/workflows/client-build.yml`. Release: `.github/workflows/client-release.yml`.
Go is pinned to `1.27.1` in `client/.go-version`; actions are SHA-pinned.
All four accepted platform binaries retain their canonical names. One
`checksums.txt` covers all four. Ordinary CI is read-only; only release publication
has `contents: write`. Compilation needs no secret.

[Installation instructions](../../../client/INSTALL.md) cover macOS arm64,
macOS amd64 and Linux/WSL amd64. No host build or SCP is required. Native
attestations and changie automation are explicitly deferred; no updater/final
installer, native Windows client or E0.D+ implementation was added.

# E0.D — Workstation identity, registration, presence and reconnect

Status: **PARTIAL**. Implementation and local deterministic validation are complete;
the persistent edge is deployed; primary Mac alpha.3 auto-registration, disconnect and reconnect passed. Post-restart reconnect and three sequential ACP sessions passed; protocol-2 client and alternate-peer acceptance remain pending. E0.C remains PASS.
Baseline: `23271871da4a27b3f86655602393756f8665dc7d`.

The [contract](../../../docs/contracts/workstation-identity.md) records storage,
identity, presence and protocol compatibility. Tailscale owns admission and strong
node revocation; Blaine automatically records admitted workstations. No second
manual approval, workspace/file/terminal authority or Task ledger was added.

## Local evidence

- Go 1.27.1; pinned tsnet v1.102.4; pgx v5.11.0.
- Shared client CI: formatting, Go tests, race checks, vet, nine installer tests,
  six host/readiness regressions, offline checks, four targets built twice with
  matching SHA-256 and exact version/protocol/commit metadata: PASS.
- Disposable PostgreSQL fixture: identity/reconnect/reload, concurrent registration,
  lease expiry/read-only inventory, malformed/unavailable storage and host inventory
  CLI: PASS under race checks. Production storage was not used for those tests.
- Deployment staging: seven tests PASS, including explicit removal of the temporary
  manual node list and idempotent adoption of the registry configuration.
- Protocol 1 compatibility is fixture-proven; protocol 2 adds signed registration
  receipt/metadata and preserves pinned transport identity. Actual client/Hub live
  observations will be recorded separately.

[Deployment evidence](deployment.json) records the exact source/binary, empty initial
inventory and unchanged runtime/Restate processes. The migration rerun passed.
[Task evidence](task-independence.json) confirms the existing controlled WAITING
Task was unchanged by edge deployment; the subsequent real IDE quit and edge restart also preserved that state.
[Validation summary](validation.json) distinguishes fixtures from live deployment.

[Alpha.4](alpha4-delivery.json) is now published through the existing Actions
release workflow, following explicit operator authorization. Source
`1c76a23a1640a5d69a0862ea8f39a32cd12a5ee1` adds only a timezone-safe inventory test
comparison to the originally prepared `86d37cb`. [CI investigation](ci-investigation.json)
retains the earlier failures, reproduction and successful corrected run. No tag
was created for a failing commit and no shared history was rewritten.

All four public downloads matched `checksums.txt` and independently built local
alpha.4 binaries. The public installer matches the tag. The Linux binary's version
was executed only after checksum verification. No generated binary was committed;
attestation/notarization and changie remain deferred. Public alpha.3 is retained
as historical E0.C/legacy-protocol evidence. E0.E/E0.F sequencing is unchanged;
full Windows IntelliJ acceptance is not an E0.D blocker.

`request.json` is an unsubmitted development request draft. No durable development
Task was created through an unavailable execution binding.

## Primary Mac live observations

The alpha.3 peer `nEEbpyYWN921CNTRL` automatically received
`ws-4f6ac6af05280a601acfd0d5eb3bce59`. The real IntelliJ `inspect e0c` exchange
returned `UNAVAILABLE`, the expected read-only control response. This is not a
transport failure. [First connection](live/mac-alpha3-first-open.json),
[complete IDE quit](live/mac-alpha3-closed.json),
[reopened IDE](live/mac-alpha3-reopened.json),
[edge restart](live/edge-restarted.json) and
[post-restart reconnect](live/mac-after-edge-restart.json) show one durable row,
ONLINE/OFFLINE/ONLINE transitions and three distinct ACP sessions with the same
workstation ID. Runtime and Restate PIDs remained unchanged.

The alpha.3 architecture field is empty: neither its Hello nor current WhoIs
metadata supplied it. No inference from hostname was stored. Protocol-2 receipt
and client-upgrade acceptance remain explicit gates for the prepared alpha.4.
[Operator inspect](live/mac-inspect.json) and
[storage access](live/storage-access.json) are read-only live observations.

# E0.D — Workstation identity, registration, presence and reconnect

Status: **PARTIAL**. Implementation and local deterministic validation are complete;
the persistent edge is deployed and primary Mac live acceptance is pending. E0.C remains PASS.
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
Task was unchanged by edge deployment; this does not yet prove the E0.D IDE quit.
[Validation summary](validation.json) distinguishes fixtures from live deployment.

The local installer/release preparation targets **v0.1.0-alpha.4**, including the
protocol-2 receipt and client metadata. It is not published or authorized for
publication yet; the public alpha.3 installer has not changed. The installer
rejects a checksum-verified binary with the old protocol before installation.
No new public release or push has occurred. Public alpha.3 remains the historical
E0.C-proven client and does not expose the new receipt. E0.E/E0.F sequencing is
unchanged; full Windows IntelliJ acceptance is not an E0.D blocker.

`request.json` is an unsubmitted development request draft. No durable development
Task was created through an unavailable execution binding.

# E0.D — Workstation identity, registration, presence and reconnect

Status: **PARTIAL**. Implementation and local deterministic validation are complete;
deployment and primary Mac live acceptance are pending. E0.C remains PASS.
Baseline: `23271871da4a27b3f86655602393756f8665dc7d`.

The [contract](../../../docs/contracts/workstation-identity.md) records storage,
identity, presence and protocol compatibility. Tailscale owns admission and strong
node revocation; Blaine automatically records admitted workstations. No second
manual approval, workspace/file/terminal authority or Task ledger was added.

## Local evidence

- Go 1.27.1; pinned tsnet v1.102.4; pgx v5.11.0.
- Shared client CI: formatting, Go tests, race checks, vet, eight installer tests,
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

No new public release or push has occurred. Public alpha.3 remains the historical
E0.C-proven client and does not expose the new receipt. E0.E/E0.F sequencing is
unchanged; full Windows IntelliJ acceptance is not an E0.D blocker.

`request.json` is an unsubmitted development request draft. No durable development
Task was created through an unavailable execution binding.

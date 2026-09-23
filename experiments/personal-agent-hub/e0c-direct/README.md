# E0.C embedded transport migration — PARTIAL

The operator selected embedded tsnet plus a direct private Blaine application
transport after the [bounded spike](../transport-architecture-spike/README.md).
Tailscale SSH remains an administrative/diagnostic facility. The prior SSH adapter
and its accepted fixture evidence are retained unchanged for comparison/rollback.
No new release, public listener, system Tailscale installation, nested WSL daemon,
E0.D registry, workspace capability or custom IDE plugin is introduced.

The [development request](request.json) is **unsubmitted**: no suitable durable
implementation-work binding was available. Controlled runtime acceptance Tasks
are separate test fixtures, not claims that this development request was submitted.

## Implementation and trust

`blaine connect` discovers the single Hub candidate from public, embedded deployment
metadata. No host/Unix-account input or workstation username inference occurs.
`blaine acp` presents ACP initialization/authentication locally, opens the normal
Tailscale browser flow when explicitly authenticated, and forwards the authenticated
session to the existing PersonalACP runtime. No IDE tools are granted in E0.C.

1. The embedded userspace Tailscale stack owns one stable private store. Its name
   derives from a persistent Blaine application key; close does not logout/reset.
2. The expected tailnet and Hub stable node ID/name must match. Startup waits at
   most 20 seconds for that particular peer map entry, addressing the measured
   spike race. `Self.Online` alone never establishes or denies connectivity.
3. Every outgoing TCP connection verifies the destination through embedded WhoIs.
   The private host listener derives the peer from its accepted socket using native
   host LocalAPI. Forwarding headers, client JSON and Unix usernames cannot nominate
   that identity. An explicit principal + stable-node allowlist constrains the host.
4. A pinned Blaine Ed25519 server key signs a nonce/session/protocol/readiness/peer
   challenge. The installation proves possession of its separate Ed25519 key with
   a domain-separated signature. Reflection, replay and identity/protocol mismatches
   fail closed. Self-certified workstation identity is not registration or authority;
   the server-observed network peer remains attached to the session for E0.D.
5. WebSocket binary frames carry an operation kind, 128-bit session ID and bounded
   bytes. ACP JSON-RPC correlation and the existing E0 capability guard still apply.
   No PTY, remote shell, Unix transport account or SSH trust file is involved.

See the [wire/storage contract](../../../docs/contracts/host-connection.md).
One process leases the installation at a time. Concurrent CLI/IDE use returns
`INSTANCE_BUSY`; no broker/runtime daemon is introduced. Restarting reconnects with
new session correlation and the same installation/node; requests are not replayed.

## Measured evidence at this checkpoint

| Evidence | Result | Scope/limit |
| --- | --- | --- |
| Client formatting, Go tests, race, vet, existing SSH/platform/process regressions | PASS | Local Linux development host; local WebSocket peers are fixtures. |
| Four target builds and byte-identical rebuilds, metadata, SHA-256 manifest | PASS | Linux amd64/arm64 and Darwin amd64/arm64 build verification, not workstation runtime proof. |
| Binary framing | PASS fixture | 1 MiB containing all byte values; server-initiated binary frame; cancellation acknowledgement; session mismatch and disconnect rejection. |
| Identity | PASS fixture | Signed server identity, client proof, wrong key/node/protocol, replay/reflection and UNKNOWN dependency rejection; exclusive/private state and stable key/node baseline. |
| Actual installed PersonalACP subprocess over new relay | PASS local integration | Real Python ACP SDK/runtime initialize + session/new + EOF cleanup over loopback fixture transport; no remote peer or Task claim. |
| Host readiness entrypoint | PASS live host | Existing runtime handlers/deployment, configured generation/embedding models, and one bounded read-only semantic MIRIX query. No returned memory content retained. |
| macOS production candidate | PASS live transport/ACP signal batch | Corrected commit `77a974c` passed two direct runs and real remote ACP SIGINT/SIGTERM exit 130. Node/application identity survived process restarts and binary replacement from `dadb3c5`. JetBrains, reboot/revocation and policy gates remain separate. |
| WSL production candidate | PARTIAL live enrollment; transport batch PENDING | Candidate `77a974c` checksum passed. Browser enrollment produced the designated installation node; the host correctly denied it before allowlisting. Independent host node/principal review completed; repeat handshake/stream/ACP/signals pending. |
| Real Blaine JetBrains launch/auth | PENDING | Windows IDE opens a WSL project. Candidate uses `wsl.exe --distribution Ubuntu --exec … blaine acp`; actual stdio/location must be measured. |
| Task independence | PASS bounded live Mac + local runtime | The same controlled Restate Task remained WAITING with identical authoritative state after local fixture disconnect, the initial Mac failure, and both successful Mac ACP signal terminations. This proves preservation of that Task, not continued execution of an active inference workload. |
| Effective narrow tailnet ACL / revocation / reboot | PENDING | Intended policy below; no tailnet policy mutation or administrative revocation claimed. |

The first native readiness run exposed an empty successful `/health` response
handling defect in the new adapter. It was fixed and the exact production probe
then returned all five PASS. The previous unconditional MIRIX `/health` remains
insufficient; the new check exercises the configured retrieval path without writes.

### macOS inherited-stdio defect

The [Mac transcript](macos-direct-before-stdio-fix.json) uses candidate commit
`dadb3c540b18bd943064f9b7a2a160cb3c3b3c2a`. Initial
[enrollment](macos-enrollment.json) correctly failed closed until the host's exact
node/principal allowlist authorized the designated product installation. Two later
runs passed the direct transport probes. Both identities persisted, with distinct
session IDs. The script then reported `STOP: ACP did not exit after SIGINT`; the
operator confirmed empty stderr. SIGTERM was not reached. Protocol cancellation
acknowledgement and graceful remote ACP EOF do not prove local OS-signal cleanup.

The same hang was reproduced on Linux without network authentication: start the
compiled client, initialize ACP, leave inherited stdin open, send SIGINT. Blocking
inherited descriptors are not necessarily enrolled in Go's poller; closing one
from a cancellation callback can wait indefinitely for its blocked read/write.
The earlier `os.Pipe` tests did not reproduce this property.

The correction uses owned descriptor duplicates, nonblocking byte I/O and bounded
POSIX poll on Linux/macOS. Cancellation interrupts both idle input and backpressured
output, including remote exit. It restores descriptor flags and leaves the original
descriptors open. The existing E0.A child descriptor/process-group path is unchanged.
Regression coverage exercises the compiled client with inherited pipes and a named
FIFO, both signals while input remains open, and blocked output. Relay fixtures also
exercise remote exit/disconnect with open blocking input. The designated Mac then
passed both signals using the corrected candidate; no new prerelease is published.
The [correction validation](stdio-fix-validation.json) records the passing complete
local client CI suite, six inherited-stdio signal cases and four reproducible
target builds. This is not a new GitHub Actions run.

The [corrected Mac live batch](macos-direct-signal-pass.json) records candidate
`77a974c31b622983bc24c7316e690d4caeafca3c`, checksum verification, two successful
1 MiB binary/handshake/ACP runs, and real ACP sessions before SIGINT/SIGTERM. Both
processes exited 130 within the script bound; `blaine: context canceled` appeared
only on stderr. The same node `nEEbpyYWN921CNTRL` and workstation ID survived the
binary upgrade. The [subsequent authoritative Task read](task-after-macos-signals.json)
matches the pre-test state exactly. `doctor` correctly remained NOT_READY: it does
not probe connectivity, and E0.D registration and integrated onboarding are absent.
This is operator-supplied live workstation evidence, distinct from local fixtures.

The [WSL enrollment](wsl-enrollment.json) records the same corrected candidate in
Ubuntu on ST00251. The new product node `nPvKcFBuW821CNTRL` was denied before its
signed Blaine handshake, as expected. The host independently verified the exact
node, expected principal, Linux platform and installation-derived name; only then
was it added beside the designated Mac in the transport allowlist. The private
candidate listener was restarted and all five dependency checks passed. No tailnet
ACL, system Tailscale, runtime or Restate service was changed. The controlled Task
remained WAITING before the repeat. The WSL stream, ACP and signal gates are still
pending; this temporary admission review is not E0.D registration.

## Identity and policy lifecycle

Private storage: `direct-v1/identity.key` (0600 Ed25519 seed), `tsnet/` (0700 and
vendor credential files), `node-id`, and a private non-authoritative `connection.json`
receipt. The receipt is saved only after the signed handshake. Identity or deployment
changes against an existing receipt fail closed. State must remain in the native
user home; do not put WSL credentials on a shared Windows download mount.

The application identity and tsnet node are stable across ordinary process/binary
replacement. Mac production-candidate binary upgrade reuse is now measured; reboot
and WSL candidate lifecycle remain live gates. The spike
already measured node reuse across Mac binary revisions; that is not silently
promoted into candidate evidence. Loss/copy of credentials requires revocation;
filesystem permissions do not protect against a compromised same-user process.

`disconnect --logout` affects the embedded node only. Explicit `--reset-identity`
requires confirmed local logout before deleting this installation's keys/store.
Remote tailnet revocation and stale-device removal are operator actions. Local
logout does not claim instant administrative removal. A subsequent changed node
cannot silently replace the old recorded binding. E0.D must correlate this transport
identity and proof of the Blaine installation key with its own durable registration.

Intended tailnet policy is an operator-owned `tag:blaine-client` (or equivalently
scoped installation identities) with access only to the Hub's TCP 7443 service.
The Hub identity/tag is distinct. Tag assignment must be authorized by tagOwners;
advertising a tag is not permission. Additive broad user/tag grants must be reviewed:
a narrow new rule does not override an existing wildcard allow. Current candidate
bootstrap does not self-assign tags or mutate policy. Host policy supports an exact
trusted user principal or an explicit trusted tag plus named stable node IDs.
The app allowlist is useful defense but does not prove that the node cannot reach
other tailnet services. Effective tailnet least-privilege remains a measured gate.

No auth key, OAuth client secret, auth URL, node credential or Hub private key belongs
in source, reports or candidate archives. The Hub public pin is deployment metadata.
tsnet's vendor diagnostic logging policy is separate from Blaine diagnostics; blank
Blaine log callbacks are not a claim that upstream telemetry is disabled.

## Operator batch and remaining gates

[accept.sh](accept.sh) consumes the same candidate repeatedly: checksum verification,
user-local install with prior-binary backup, metadata/doctor, two real connect +
stream + ACP checks, followed by real ACP startup and SIGINT/SIGTERM cleanup. First enrollment reveals the public node ID; the host operator
must authorize only the two designated product installations. The experimental
spike nodes are not silently imported or deleted. No additional download is needed
for that review. [OPERATOR.md](OPERATOR.md) contains the subsequent exact IDE entries.

Still required: WSL reports; half-open/revocation behavior on
those platforms; reboot and WSL upgrade identity observation; host deployment persistence;
least-privilege policy evidence; real JetBrains launch/auth; and the unrelated durable
Task surviving session termination. Do not publish another prerelease or call E0.C
PASS before its live gates pass. E0.D remains blocked and is the next canonical slice
only after E0.C acceptance. E0.E/F still own full onboarding/configuration acceptance.

Retained observations: [host readiness](host-readiness.json), [real ACP subprocess](installed-acp.txt),
[Task before](task-before.json), [Task after local disconnect](task-after-local-disconnect.json),
[Task after initial Mac termination](task-after-macos-disconnect.json),
[Task after corrected Mac signals](task-after-macos-signals.json), and [summary](summary.json).
The controlled Task remains at its human wait for the
designated-workstation comparisons; it is not the implementation Task.

[Local CI transcript](client-ci.txt) and [four-target build validation](build-validation.json)
record the uncommitted validation build, not a published release or new GitHub
Actions run. A final candidate can embed the resulting local source commit;
publication remains blocked on live acceptance.

[Final race regression](final-race.txt) and [24 runtime regressions](runtime-tests.txt) passed.
The runtime tests required host execution after their sandboxed asyncio run stalled;
only that test process was stopped. No runtime service was interrupted.

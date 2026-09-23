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
| WSL production candidate | PASS live batch; normal-launch PASS operator-reported | Detailed `77a974c` diagnostic-MTU reports prove binary/ACP/signals. The operator also confirmed PASS for requested `478a0f1` normal launch; new host logs corroborate complete binary/ACP sessions. Exact latest client metadata/MTU-source JSON remains to be retained. |
| Real Blaine JetBrains launch/auth | PENDING | Windows IDE opens a WSL project. Candidate uses `wsl.exe --distribution Ubuntu --exec … blaine acp`; actual stdio/location must be measured. |
| Task independence | PASS bounded live Mac/WSL + local runtime | The same controlled Restate Task remained WAITING with identical authoritative state after local fixture disconnect, both Mac ACP signal terminations, and two real WSL remote ACP sessions ending with the MTU override. This proves preservation of that Task, not continued execution of an active inference workload. |
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

The [first admitted WSL repeat](wsl-direct-write-timeout.json) reused both IDs but
exited 3 with `failed to write msg: failed to write frame: context deadline exceeded`.
Only the probe scope was emitted. The executable enters that probe after completing
the initial authenticated handshake and its Exit frame; this is a control-flow
inference, not a captured final CONNECTED receipt. Existing diagnostics cannot
separate the probe's own handshake write from its first binary write. Do not call
this a DNS, SSH authorization, WSL topology or downstream-readiness failure.
The host remained active and all dependency checks passed afterward. The
[controlled Task snapshot](task-after-wsl-timeout.json) remained unchanged.

The candidate host now has bounded stage observations for authenticated handshakes,
probe greeting/receive/echo and session completion: elapsed time, byte count, public
peer/session IDs and fixed error categories only. Frame contents, raw errors, auth
URLs and credential material are excluded; at most 32 probe-stage events are emitted
per session, plus handshake and completion events. Tests cover stage reporting,
byte counts and error/payload redaction; all client Go tests with race detection and
vet passed. No protocol, timeout, authorization or workstation binary changes are
made for this diagnosis. No cause or successful WSL stream is claimed yet.

The [repeat with host-stage correlation](wsl-direct-timeout-correlated.json) now
proves both signed handshakes at the host, for the admitted WSL node. The initial
session ended normally; the probe sent its seven-byte binary greeting and waited
for the next frame until its 15-second deadline. No echo began. The exact client
code validates that greeting before attempting the 1 MiB write, which returned the
reported timeout. The logger does not measure partial TCP bytes: failure to receive
a complete application frame is not evidence of zero packets arriving.

The cause remains unresolved. The next read-only workstation observation is
`ip -o link show`. Current [official Tailscale WSL guidance](https://tailscale.com/docs/install/windows/wsl2)
documents packet-size limitations, including a 1280-byte underlying interface MTU
and encrypted traffic crossing Windows-owned Tailscale. This motivates inspection;
it does not establish either condition for this embedded-tsnet run. No daemon
installation, interface change, debug override, deadline extension or topology
change has been made. Effective path MTU and offload behavior remain hypotheses.

The operator then measured `eth0` MTU **1280**. The controlled
[process-local MTU experiment](wsl-mtu-probe-pass.json), using
`TS_DEBUG_MTU=1200 bash accept.sh`, passed both full 1 MiB binary probes with the
same expected digest, cancellation/deadline/reconnect checks and real remote ACP
sessions. The host independently recorded each 1 MiB echo completing at 90/87 ms
from its probe handshake start. Node/application identity remained unchanged and
the [controlled Task state](task-after-wsl-mtu-probe.json) was identical afterward.
This is strong measured support for an MTU-dependent transport failure, with no
smaller test payload, extended timeout, weakened identity gate or OS-interface edit.
The pinned [upstream MTU implementation](https://github.com/tailscale/tailscale/blob/v1.102.4/net/tstun/mtu.go)
accepts that diagnostic override and budgets up to 80 bytes for encapsulation.
This temporary override is **not** the accepted production UX or an automatic
adapter fix. A normal-launch candidate repeat remains a gate; IPv6-only paths are
an unverified limitation.

That run stopped before SIGINT at `mkfifo: File exists` in a newly created report
directory under the Windows download mount. Its filesystem-level cause has not
been proved; no signal failure is inferred. Repeating the unchanged, checksum-verified
four package files from a fresh directory under the Linux home was requested.
The repository harness now places report/FIFO files under the native home and
preflights FIFO creation before live probes. It does not touch installation keys,
mount options or Windows configuration. Existing packages are unchanged and need
no replacement for the native-home comparison. Shell syntax validation passed.

The [native-home WSL repeat](wsl-mtu-signal-pass.json) then passed the entire batch:
two 1 MiB binary probes with the expected SHA-256, real ACP sessions and both local
OS signals exiting 130. The copied four package files retained their checksums;
node/application identities were unchanged. The host confirmed all sessions ended
and the [authoritative Task snapshot](task-after-wsl-signals.json) remained identical.
This establishes signal acceptance with the diagnostic MTU override. It does not
establish that the unchanged product defaults work on that interface.

The automatic-MTU candidate correction inspects the WSL default-route interface
without a CLI, OS network writes or elevated privileges. The measured MTU 1280 case
sets embedded MTU 1200 before startup; other supported platforms keep their default.
tsnet v1.102.4 has no per-Server MTU field, so the bridge uses its process-local
`TS_DEBUG_MTU` lookup, isolated behind the client adapter. It is explicitly a pinned
SDK dependency, with a subprocess test proving the actual SDK consumes the setting;
it must be reviewed on dependency upgrades. Read/unknown-route failures fail closed;
manual diagnostic overrides are bounded and marked separately in connection output.
Normal startup needs no operator flag or environment variable. No live no-override
result is claimed until the corrected candidate runs on the designated WSL peer.
The [automatic-MTU validation](wsl-mtu-validation.json) records final local CI PASS:
formatting, Go tests/race/vet, offline process/stdio regressions, host unit tests and
four reproducible target builds. The initial complete run failed the preexisting
process-descendant cleanup test; the PID was absent after test cleanup, five targeted
package repetitions passed, and the subsequent full suite passed. That initial
observation remains unexplained and is retained as a validation limitation. Process
cleanup implementation was not changed by the MTU correction.

The operator subsequently confirmed that the requested **normal** `bash accept.sh`
batch passed with the automatic-MTU candidate. The
[normal-launch checkpoint](wsl-automatic-mtu-pass.json) distinguishes this concise
confirmation from the earlier full client transcripts: the exact new version,
MTU-source JSON and report-directory name were not supplied. Independently read
host logs contain four further complete 1 MiB echoes, authenticated sessions for
the same designated node and ACP session teardown. This window contains two batches;
it is not falsely assigned to a single unavailable client report. The
[Task state](task-after-wsl-automatic-mtu.json) is still identical to the pre-WSL
snapshot. The normal-launch result is operator-reported PASS; the final dossier
must retain the exact client metadata/MTU-source record. Real JetBrains launch/auth
and remaining lifecycle, policy and host-deployment gates stay open.

## Development IDE installer checkpoint

The initial Python-based installer ([historical validation](installer-validation.json))
was superseded before real IDE acceptance at the operator's direction. The shell
bootstrap now downloads only **alpha.2**, verifies its published checksum before
execution, and delegates JSON handling to `blaine integration jetbrains install`.
`blaine integration jetbrains check [--json]` is read-only. No workstation Python,
SSH, system Tailscale, host selection or candidate-directory flow is required.
Existing agents and global policy are preserved; malformed/duplicate-key JSON,
ambiguous Blaine entries and unsafe files fail closed. One bounded backup retains
the prior valid config. The actual Windows IDE/WSL launch topology is kept explicit.

The operator authorized alpha.2 publication despite remaining E0.C gates to enable
public-installer IDE acceptance. [Alpha.2 delivery](alpha2-delivery.json) records
source, build, release and actual platform evidence. Alpha.2 publication and the
[public Linux installer](alpha2-public-installer.json) passed: all four published
binaries match the local exact-source builds, and installation/check/reinstallation
preserved an existing agent in an isolated home. Mac and WSL operator/IDE proof
remain pending. Publication does not establish
real IntelliJ launch/auth. E0.C remains PARTIAL and E0.D is blocked. ACP Registry,
not this development bootstrap, remains the final distribution direction.

## Alpha.2 real IDE launch and local envelope correction

The designated Mac operator installed through the public alpha.2 path, restarted
IntelliJ and selected Blaine. The process launched but exited with code 3:
`json: unknown field "type"`. This is **not** a successful real IDE ACP session.
The exact error was reproduced with the published Linux asset and a reconstructed,
non-sensitive initialize envelope. No captured IDE payload or credentials are
retained. [Correction evidence](acp-envelope-fix.json) distinguishes the live report
from fixture evidence and records passing full client regressions.

The correction accepts an optional auxiliary string `type` in the local ACP
request envelope. It grants no capabilities and does not change tsnet, server
identity, private handshake validation, JSON ambiguity checks or protocol versions.
The operator explicitly authorized an exact-commit Mac candidate **before** any
alpha.3 publication. This controlled exception to public-release acceptance does
not change the public installer or authorize publication of another release.
The operator subsequently authorized alpha.3 publication to avoid another local
ZIP transfer. The public installer target is now alpha.3; [delivery status](alpha3-delivery.json)
records measured results. The next gate remains a real IntelliJ-launched ACP
session through the private Hub. No successful fixed Mac IDE session is inferred
from the local tests or release publication.

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

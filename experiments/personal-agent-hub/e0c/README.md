# E0.C — Host profile, transport and handshake

**PARTIAL — client/control/framing candidate and local Linux observations.**
E0.C is not accepted. The user designated `blaine` / `leofuso` and explicitly left
the second-workstation peer-identity proof **PENDING/BLOCKED** until a workstation
is provided. No other tailnet device was selected or contacted.

E0.A and development-platform E0.B remain accepted. Full E0 remains unaccepted.
No E0.D registration, E0.E IDE configuration or E0.F integrated acceptance was
implemented. No workspace read/write/exec, coding behavior, public gateway,
Keycloak/OIDC or IntelliJ plugin was added. The initial checkpoint was local-only.
Subsequent explicitly authorized [delivery support](delivery.md) published the
E0.C branch and first alpha Release; no merge occurred.

The [TaskSpec](request.json) is **unsubmitted**: no suitable durable development
Task binding was exposed. Local implementation was explicitly authorized. No
runtime Task identity, state or background execution is claimed.

## Implemented candidate and boundary

The [contract](../../../docs/contracts/host-connection.md) and
[client guide](../../../client/README.md) describe the exact implemented subset.

- Explicit host selection, native MagicDNS short-name qualification, private-route
  checks, platform-native profile paths and private atomic first publication after
  verified host identity/readiness. Existing/concurrent profiles are preserved;
  re-pairing is not automatic. Client UUID is metadata, never a credential.
- Narrow native OpenSSH adapter: strict known-host checking, explicit user,
  `none` authentication for Tailscale SSH, no password/key fallback, PTY,
  user SSH configuration, multiplexing, forwarded agent or ports. No network
  listener, tailnet admin API, credential persistence or infrastructure changes.
- Separate bounded handshake request/response validation: pinned server identity,
  protocol intersection, required features, trusted-peer observation fields,
  registration explicitly unimplemented, and required readiness. Control stdout
  never shares ACP framing. Raw control diagnostics are not exported.
- Bounded NDJSON/JSON-RPC ACP guard: duplicate-key/encoding/size checks, matched
  request IDs, pending-request limits, banner/truncation/unknown-response rejection,
  and stream/resource cleanup under EOF, cancellation and backpressure. Session
  loss never creates, resumes, cancels, approves or completes a Task.
- E0 strips advertised client capabilities, rejects nonempty MCP descriptors and
  host client-capability calls, and permits passive session updates. It grants no
  workspace authority. The original E0.A arbitrary-byte fixture stays separate.
- A host control candidate with pure negotiation/readiness functions and a
  **fail-closed entrypoint**. Its production peer resolver and successful control/
  ACP dispatcher are **not implemented**. No successful remote handshake, paired
  profile or real PersonalACP launch was achieved. The entrypoint rejects before
  reading caller data; no environment, argument or JSON switch bypasses that gate.

The host candidate was copied to a disposable home's stable
`.local/bin/blaine-host-connection` path and executed there. This proves its local
rejection behavior outside the checkout, **not production deployment**. No
installed Blaine runtime/service was changed. Finishing and deploying the host
boundary remains E0.C work after trusted binding is established.

## Live development-host observations

[Live evidence](live.json), 2026-09-22, native Linux amd64:

| Observation | Result and limit |
| --- | --- |
| Tailscale `1.102.4`, `RunSSH: true` | Existing daemon reports SSH enabled; this does not establish the mode of a particular connection. |
| Short `blaine` lookup | Resolves outside the host's tailnet addresses (local loopback collision). Qualification through native MagicDNS metadata resolves to this host's actual tailnet addresses. No guessed suffix or tailnet scan. |
| Self-route SSH banner | `OpenSSH_10.2p1`, not a remote Tailscale SSH session. It is not accepted as peer-identity proof. |
| `connect --non-interactive --host blaine`, twice | Both return `REMOTE_UNAVAILABLE`, exit 3; no profile/state persisted, no fallback, no false handshake/READY claim. |
| Doctor | `NOT_READY`, exit 2; no client-state writes. |
| Staged host `handshake` and `acp` with spoofed peer environment | Both return `PEER_UNVERIFIED`, exit 2, exactly zero stdout bytes. This is a local process test. |
| Runtime / Restate | Read-only discovery finds the expected runtime handlers and configured deployment/URI/service. |
| Generation / embeddings | Read-only health/model-list checks find the configured models; no inference request. |
| MIRIX | `UNKNOWN`: its installed `/health` returns liveness without dependency checks. It cannot satisfy required readiness. |
| Before/after native network identity/address observations | Unchanged. No installation, login/logout, daemon mutation or preference change. |

The original sandbox could not reach the local daemon socket; read-only host
execution supplied the actual observations. No unavailable sandbox response was
counted as a host outage. The initial live harness rejected the short-name route
before opening a connection; its native MagicDNS qualification correction then
passed. The successful retained run still does not claim a second peer.

[Source observations](sources.json) record version-matched public Tailscale code
inspected for the gate. The non-PTY Linux incubator can exec `su`; its original
peer argv is not a proven launcher contract. `SSH_CONNECTION` in a caller's own
environment can be overwritten, and `whois` on a claimed address does not bind
that caller. No speculative `/proc` ancestry, broad privilege or shared secret
was adopted. This is a pending verification boundary, not a claim that Tailscale
SSH can never provide suitable identity.

## Fixture and build evidence

| Evidence | What it proves |
| --- | --- |
| [tests.txt](tests.txt) | Client regressions plus host/profile/handshake/framing cases: concurrent publication, unsafe config/host inputs, MagicDNS metadata, private address restrictions, required SSH flags, identity/user/server mismatch, protocol/feature/readiness rejection, removed/revoked-style response rejection, control separation and deadlines, and framed subprocess behavior. |
| [host-tests.txt](host-tests.txt) | Pure Python host negotiation, claimed peer rejection, unavailable production identity, malformed JSON and truthful readiness projection. |
| [race.txt](race.txt), [static.txt](static.txt) | Go race instrumentation and vet passed. |
| [offline.json](offline.json) | Accepted E0.A/B standalone byte/process regression reused without changing its historical evidence: no repo/runtime/PATH dependency, byte equality, stderr isolation, streaming, exits/deadlines/signals and no fresh client state. |
| [build.txt](build.txt), [builds.json](builds.json) | Four standalone artifacts, identical repeat-build hashes, formats, sizes, toolchain, exact source hashes and Linux amd64 without a dynamic interpreter. |
| [docs.txt](docs.txt), [summary.json](summary.json) | Documentation consistency, JSON validation, diff check and scoped acceptance summary. |

Offline/host-key-mismatch/check-mode-required/check-mode-waiting behaviors use
synthetic subprocesses, **not live tailnet policy changes or browser reauthentication**.
Framed duplex, banner rejection, unanswered requests, nonzero exit, EOF and blocked
output use real pipes/processes with synthetic peers. No fixture establishes a
trusted device or live remote ACP session. Fresh installation/login remains the
separate E0.B limitation.

Initial verification caught an incorrect build-info field and a stale E0.B flag
expectation. A race run exposed shutdown handling that confused closed input with
malformed traffic; closed-descriptor handling was corrected, and the normal-exit
fixture now consumes its request before exiting. Final regular/race checks passed.
No failed attempt was counted as acceptance.

## Platform acceptance matrix

| Platform | Designed | Build-verified | Runtime-verified for E0.C | Status |
| --- | --- | --- | --- | --- |
| Linux amd64 development host | Yes | Yes, static ELF | Local DNS/SSH observations, fail-closed connect/doctor/host processes, read-only readiness; no second-peer handshake/ACP | PARTIAL |
| Linux arm64 | Yes | Yes | No | Unverified |
| macOS amd64 / arm64 | Native Tailscale + OpenSSH and Application Support paths | Both Mach-O targets | No | Unverified; no all-platform readiness claim |
| Windows + WSL2 | Native Windows network ownership, distro client and separately gated guest route | Linux binaries only | No designated WSL workstation | PENDING/blocked; inherited E0.B reuse gate, no second daemon or forwarding changes |

## Remaining gates and exact next slice

1. Provide the designated second tailnet workstation; do not repurpose a device.
2. From it, establish intended host-key trust and prove the actual Tailscale SSH
   mode, authenticated source/device/principal and `leofuso` mapping. Retain
   negative spoof/mismatch and check-mode behavior. Implement only a verifiable
   host binding; stop for review if the documented mechanism cannot satisfy it.
3. Complete the host dispatcher, dependency-aware MIRIX readiness and bounded
   stable entrypoint deployment. A fixture-ready response is not a deployed service.
4. Run real separate handshake and remote ACP framing/cleanup acceptance, including
   offline, wrong-host/key, protocol mismatch, check-mode and stdout corruption.
5. Record native macOS and Windows+WSL2 live results separately before claiming
   those platforms. WSL forwarding need remains unmeasured.

**E0.C remains the active acceptance gate. The exact next canonical slice is
E0.D — Registration, after E0.C is accepted.** E0.E and E0.F remain afterward.
No later-slice implementation was pulled forward. The accepted architecture and
ADR 0022 are unchanged.

## Reproduce

```bash
BLAINE_GO=/tmp/blaine-e0a-toolchain/go/bin/go \
GOCACHE=/tmp/blaine-go-cache GOPATH=/tmp/blaine-go-path \
experiments/personal-agent-hub/e0c/verify.sh

# Separately, read-only on the designated development host itself:
python3 experiments/personal-agent-hub/e0c/accept_live.py \
  .local/e0c-artifacts/blaine-linux-amd64
```

The live script asserts the target is this host before contacting it. It never
selects another peer or changes native SSH trust. Artifacts stay in ignored
`.local/e0c-artifacts/`. Embedded build metadata records the pre-commit base plus
`-dirty`; the retained source hashes and enclosing local commit identify the
actual implementation. No release distribution is claimed.

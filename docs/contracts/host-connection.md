# E0.C direct private host connection — candidate v1

The operator selected embedded tsnet plus a direct Blaine application transport on
2026-09-23. Implementation and [evidence](../../experiments/personal-agent-hub/e0c-direct/README.md)
are **E0.C PASS**; designated Mac transport/ACP probes, corrected OS-signal cleanup,
real IntelliJ read-only round trip and final deployment/policy proof passed. WSL
transport/ACP/signals passed with a diagnostic MTU override and the
operator reported a subsequent normal-launch automatic-MTU PASS; its exact client
metadata record and integrated acceptance remain pending. This supersedes
the previous SSH product-transport contract, retained in Git and the
[prior E0.C evidence](../../experiments/personal-agent-hub/e0c/README.md). Tailscale
SSH is still useful for administration. Protocol version 1 is pre-stability: the
new `blaine.e0c.v1` WebSocket endpoint is not the old SSH control invocation.

## E0.C closure boundary

The designated macOS workstation is the primary live E0.C peer. Its measured
restart/reconnect and binary-replacement reuse of the same tsnet node and Blaine
installation identity satisfies the minimum persistent transport identity gate.
The real IDE read-only round trip and preserved Task after IDE quit are accepted
transport evidence. Full registration, explicit revoke/reset/re-enrollment beyond
that minimum proof belong to E0.D; full second Windows/WSL IntelliJ acceptance
belongs to E0.F. Separate reboot/lifecycle observations are not newly added E0.C
blockers. Existing WSL transport evidence remains valid within its measured scope.

The final [closure](../../experiments/personal-agent-hub/e0c-direct/closure.json)
verifies effective narrow tailnet policy and canonical persistent Hub deployment,
followed by the primary Mac repeating the real IDE round trip. Vendor policy tests
and the live compiled filter prove the network restriction; an enabled, non-transient
user service with existing linger replaces the one-day candidate. No actual host
reboot is claimed. E0.D registration is unblocked and not implemented.

## Discovery and independent trust boundaries

Public embedded deployment metadata nominates `blaine.tail0f2ece.ts.net:7443`, the
expected tailnet, stable Hub node ID, Blaine server ID and its Ed25519 public key.
`blaine connect` requires no host, SSH user or manually trusted fingerprint.
Discovery does not authenticate. Each TCP dial uses embedded tsnet and verifies
its actual remote address against the expected Tailscale stable node ID. The host
binds only its verified private Tailscale address; it cannot use a public listener.

The host calls native LocalAPI WhoIs on the accepted TCP socket, ignores forwarding
headers and applies its exact principal/stable-node allowlist. Expired nodes fail.
This is network admission, separate from possession of the Blaine installation key,
future workstation registration, and per-operation Task/workspace authority.
No E0.D registry or E1/E2 authority is created by this contract.

## Application handshake

`GET /v1/session`, subprotocol `blaine.e0c.v1`, compression disabled. Redirects and
browser-origin requests are denied. Control JSON is strict UTF-8, duplicate/unknown
fields rejected, maximum 64 KiB, ten-second handshake deadline.

1. Client sends `schema`, `min_protocol`, `max_protocol`, `client_version`,
   `expected_server_id`, `client_id`, `client_public_key`, random `nonce`, and
   `mode` (`handshake`, `acp`, or bounded `probe`). Schema/protocol initially 1.
2. Server returns `schema`, selected `protocol`, `server_id`, `server_version`,
   `server_public_key`, random `session_id` and `nonce`, observed `peer`
   (`node_id`, `principal_id`), `readiness`, `registration: not-implemented`, and
   `signature`. The Ed25519 signature binds the complete hello/challenge transcript.
   The client checks the independent embedded application pin and that the observed
   client node is its own current embedded node.
3. Client returns a signature over a domain-separated client-proof transcript.
   Server checks key possession before acknowledging `session_id`, `status: CONNECTED`.
   The workstation ID is `ws-` plus the first 128 bits of SHA-256(public key); server
   ID uses `hub-` and the same derivation. IDs alone never authenticate.

Both ends require PASS for runtime, Restate, MIRIX, generation and embeddings.
UNKNOWN/FAIL cannot be bypassed by a request mode. The host uses bounded local
read-only checks, including a semantic MIRIX query under its existing deployment
identity. Memory content and credentials are never included in the handshake.

## Session framing and lifecycle

Binary WebSocket messages contain one kind byte, 16 raw session-ID bytes, then up to
1 MiB of payload. Kinds: `1 Data`, `2 End`, `3 Cancel`, `4 Exit`. End/Cancel have
empty payloads; Exit carries one status byte. Wrong session, kind, size, text frame,
malformed ACP or unmatched JSON-RPC response fails closed. WebSocket/TCP provide
ordering and backpressure. Writes have bounded deadlines. No shell quoting/text
conversion touches payloads. The bounded probe exchanges arbitrary binary values;
ACP mode carries complete newline-delimited JSON-RPC frames and applies its existing
correlation and capability guard. ACP initialization strips client capabilities;
nonempty MCP forwarding and server-initiated client effects are denied.

ACP prompt content is distinct from negotiated client capabilities. The host accepts
baseline text and resource-link blocks, as required by the
[ACP initialization contract](https://agentclientprotocol.com/protocol/v1/initialization).
In E0.C, resource links are inert references: their URIs are never resolved and
their names/descriptions/metadata never become executable control text. The response
explicitly states that attached resource context was not used. Only text blocks enter
the existing bounded control parser. A link-only prompt cannot initiate an operation;
unadvertised image/audio/embedded-resource input still rejects before dispatch.
Accepting a reference grants no filesystem, MCP, terminal or Task authority.

A connection is capped at 30 minutes in this candidate; client reconnect creates a
fresh authenticated session and never replays operations. An ACP session uses a
fixed host Python entrypoint, with direct inherited pipe descriptors and a new
process group. EOF has a five-second graceful child-exit bound. Transport failure,
cancellation or deadline kills only that ACP group. Periodic peer revalidation and
WebSocket ping detect idle loss; actual remote-revocation latency is not yet proved.
The host runtime and Restate are independently owned services. No session teardown
calls Task cancel/complete/approve, restarts a Task, or terminates those services.

The local ACP frontend/relay borrows inherited stdio through owned duplicates with
nonblocking byte I/O and bounded POSIX poll. Context cancellation interrupts idle
input and backpressured output without closing a blocking inherited descriptor
from another goroutine. Cleanup joins relay goroutines, restores descriptor flags
and closes only the duplicates. This leaves E0.A child descriptor forwarding intact.

## Installation state and commands

One exclusive lease guards `direct-v1` under E0.A native state paths. Directories
are private (0700); seed/metadata files are private regular files (0600), owned by
the user, without symlink/hard-link redirection. Embedded credential files are also
checked on reopen. A persistent application key gives the installation a stable
name; a node baseline detects unexpected identity replacement. A verified private
connection receipt binds deployment and installation metadata, but is not an E0.D
registration receipt or proof of current readiness.

`connect` authenticates interactively if necessary. `--non-interactive` fails on
missing/expired enrollment. Optional `--verify-transport` runs the bounded binary,
cancel/deadline/reconnect and real remote ACP initialize/session checks.
`acp` uses standard agent-owned auth methods and `authenticate`; before authentication
`session/new` returns auth-required. `doctor` remains read-only, does not start tsnet
or write state and cannot report cached connection evidence as fresh readiness.
`disconnect --logout` logs out embedded tsnet. Explicit `--reset-identity` additionally
removes its application/node identity only after logout succeeds. Ordinary close
never logs out or deletes identity. System Tailscale and unrelated Tasks are untouched.

Simultaneous Blaine processes fail `INSTANCE_BUSY`; no background broker, workstation
runtime, updater, registration database, workspace effects or IDE plugin is added.

## WSL packet-size compatibility

The designated WSL interface has MTU 1280. Default embedded settings completed
handshakes but repeatedly stalled the 1 MiB frame; the same binary and identities
passed full transport/ACP/signal acceptance with an internal MTU of 1200. Before
embedded startup, the candidate now inspects the WSL default-route interface using
read-only native APIs. Only the measured 1280 case selects 1200, leaving space for
up to 80 bytes of encapsulation. Linux outside WSL and macOS retain SDK defaults.
No interface, route, machine-wide environment, credential or system daemon changes.

Pinned tsnet v1.102.4 exposes no per-Server MTU setting; the adapter uses its
process-local `TS_DEBUG_MTU` lookup before `Server.Start`. This compatibility bridge
is internal to the client and must be reviewed on SDK upgrades. Startup does not
implement ongoing path-MTU adaptation. Unknown WSL default-route MTU fails with an
actionable network error. Explicit diagnostic overrides are validated and identified
as such in connection evidence; normal use requires no environment variable.
Connection observations report `embedded_mtu` and `mtu_source`. The application
frame limit remains 1 MiB. IPv6-only paths are unverified; acceptance here uses the
canonical private IPv4 Hub listener. The operator reported a normal-launch PASS;
the final acceptance dossier still needs that run's exact MTU-source metadata.

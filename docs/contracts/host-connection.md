# E0.C host connection contract v1 — PARTIAL implementation

The [canonical E0.C slice](../personal-agent-hub.md#implementation-decomposition)
owns scope and acceptance. This contract records the implemented candidate wire
format, not a new identity mechanism. [Evidence](../../experiments/personal-agent-hub/e0c/README.md)
distinguishes fixtures, local observations and remaining live gates.

## Profile and transport

`connect --host NAME` selects one explicit MagicDNS host; no tailnet enumeration.
The first SSH user defaults to the local OS account. This acceptance targets
`blaine` / `leofuso`. A successful handshake atomically publishes a private config
file with `schema_version: 1`, `host`, `ssh_user`, `transport: "tailscale-ssh"`,
random client UUID metadata and the verified `server_id`. The UUID is not a
credential. Failed negotiation writes nothing. Existing profiles are never
silently replaced; identity changes or malformed/unsafe files require review.
Native platform paths remain those established in E0.A. No tokens, keys,
conversation, workspace content, registration or Task state are stored.

The adapter resolves the selected host once, rejects addresses outside Tailscale's
IPv4/IPv6 ranges, and passes that resolved address to native OpenSSH. DNS provides
routing, not identity. Strict native known-host trust is required under the profile
host alias. On first use the operator must establish that trust through a separately
verified native SSH procedure; Blaine neither accepts unknown keys nor edits trust.
This trust bootstrap is not live-accepted in E0.C yet.

OpenSSH receives no PTY, user SSH configuration, multiplexing, forwarded agent,
port forwards, local commands, password/key fallback or interactive prompts.
Authentication is restricted to `none`, as used by Tailscale SSH; ordinary sshd
is not selected as a fallback. The chosen command is fixed:

```text
exec "$HOME/.local/bin/blaine-host-connection" handshake
exec "$HOME/.local/bin/blaine-host-connection" acp
```

The candidate host entrypoint is `runtime/host_connection.py`, installed only in
a disposable test home in this checkpoint. It uses host Python standard-library
facilities; the standalone workstation executable has no Python requirement.
There is no production host installation or remote ACP launch claim. macOS uses
native OpenSSH and native Tailscale routing by design. WSL refuses transport until
the Windows-owned guest route and identity spike passes; no fallback or forwarding
change is attempted.

## Separate bounded handshake

Handshake is a separate control invocation, never prepended to ACP stdout.
Client control operations have a five-second deadline and a 1 MiB output bound;
host request parsing is bounded to 64 KiB. Duplicate keys, trailing JSON, unknown
handshake fields and invalid UTF-8 are rejected. SSH diagnostics are not reflected
into control JSON or exported diagnostics. An SSH/control failure asks the user
to check trust, access, terminal check-mode reauthentication and the host installation.
The current adapter cannot distinguish those failure causes from exit status
alone; it reports `REMOTE_UNAVAILABLE` rather than inventing authentication state.

Request fields:

| Field | Meaning |
| --- | --- |
| `schema_version` | `1` |
| `client_version` | Installed client version |
| `protocol` | `{ "min": 1, "max": 1 }`; separate from ACP version |
| `expected_server_id` | Empty on first use; pinned server ID afterward |
| `client_id` | Random local installation metadata |

Response fields:

| Field | Meaning |
| --- | --- |
| `schema_version`, `server_id`, `server_version` | Envelope and host installation identity/version |
| `protocol`, `selected_protocol` | Server range and explicit intersection, initially `1` |
| `peer` | `device_id`, `principal_id`, `ssh_user`, `source: "trusted-transport"` |
| `registration_status` | `not-implemented` in this isolated slice; no registration receipt |
| `features` | Required `handshake-v1`, `acp-ndjson`, `no-workspace-effects` |
| `readiness` | `runtime`, `restate`, `mirix`, `generation`, `embeddings`: `PASS`, `FAIL`, `UNKNOWN` |

The response's `peer` is an observation supplied by the trusted host boundary.
A string saying `trusted-transport` is not itself proof. The production entrypoint
currently refuses every invocation with `PEER_UNVERIFIED` and empty stdout;
there is **no production peer resolver or successful handshake/ACP dispatch**.
Pure negotiation functions accept injected observations only in unit tests. There
is no CLI, environment or request-JSON fixture override. Supplying `SSH_CONNECTION`
and then looking up that claimed address does not authenticate the caller.
Implementing a verifiable resolver requires the designated second-workstation
spike. No shared credential, alternate IdP, root requirement or guessed process
ancestry was introduced to bypass it.

Every required readiness value must be PASS before the client persists a profile
or launches ACP. Runtime discovery checks actual `CognitiveTaskV1` handlers;
Restate checks the configured deployment ID/URI/service; model health and model
lists are read without inference. Fixed loopback URLs disable proxies/redirects,
with bounded parallel probes. Installed MIRIX `/health` is unconditional liveness,
so it remains UNKNOWN pending a dependency-aware predicate. These checks are
local fixture/live probe evidence, not a completed remote readiness operation.

## ACP framing and lifecycle

The candidate bridge admits bounded newline-delimited JSON-RPC 2.0 frames with
strict JSON validation, request ID preservation, duplicate/outstanding ID bounds
and matched responses. It rejects banners, partial/oversized frames, unmatched
responses and malformed envelopes before those bytes reach the IDE. Supported
frames retain their bytes, except initialization deliberately advertises empty
client capabilities in E0. Nonempty MCP descriptors and host-initiated client
capability calls are rejected; passive `session/update` notifications are allowed.
No read, write or terminal capability can be acquired in this slice.

EOF allows one second of graceful transport shutdown; cancellation, protocol
failure or blocked drainage closes owned streams/processes. There is no automatic
reconnect or replay. These are session resources, never Task cancellation,
completion, approval or creation. The accepted raw E0.A byte fixture remains
separate and unchanged; it is not remote ACP evidence.

## Remaining acceptance

Provide a designated second workstation, establish the native host-key trust,
prove installed Tailscale SSH mode and a trusted source/device/principal/user
binding, then complete the host dispatcher and install it at the stable path.
Resolve MIRIX dependency readiness without treating liveness as health. Run real
handshake/ACP stdio plus mismatch, offline and check-mode reauthentication tests.
Fixtures cannot close those gates. E0.D registration follows accepted E0.C;
E0.E IntelliJ and E0.F integrated onboarding remain untouched.

# E0.D workstation identity, inventory and presence

Implementation status: **PARTIAL — deterministic acceptance passed; live E0.D
edge deployed; designated-peer acceptance pending**. [Evidence](../../experiments/personal-agent-hub/e0d/README.md).
E0.C remains PASS. No E0.E/F or E1 capability acceptance is implied.

## Three boundaries

- Tailscale/tsnet: authenticated network identity, service admission and strong
  device revocation. Only sockets accepted on the verified private Hub listener
  are eligible. Host LocalAPI WhoIs supplies the stable node and principal;
  request headers, addresses and client claims cannot supply that identity.
- Blaine: automatic durable identity, inventory, descriptive metadata and presence
  after the existing server/client-key/protocol/dependency handshake checks.
  There is no second manual approval or host-side device allowlist.
- Workspace authority + Task authority + PolicyGate: operation authority.
  Registration grants none. The existing ACP guard still rejects unsolicited
  file/terminal effects; resource links remain inert references.

This single-owner deployment trusts Tailscale's effective service policy. Network
membership alone is not the admission rule. An application flag cannot protect
against a device retaining privileged administrative access to the Hub. No
retired/revoked state machine, node-revocation tool or independent PKI is added.

## Durable model and storage

Use the existing native PostgreSQL instance, isolated logical database `blaine`,
schema `blaine_workstations`, migration version 1. The existing Hub service OS
account authenticates locally through the Unix socket with peer authentication;
it receives only CONNECT, schema USAGE, schema-version SELECT and DML on the two
registry tables. PostgreSQL owns the schema. No password, new database engine,
root daemon, HBA change or vendor database migration is required.

`workstation` contains:

| Field | Meaning |
| --- | --- |
| `workstation_id` | Hub-generated random 128-bit ID with `ws-` prefix; immutable. |
| `tailnet`, `transport_node_id` | Unique authenticated transport binding. |
| `principal_id` | Observed user/tag reference; descriptive binding evidence. |
| `installation_id` | Latest proven application-key-derived ID; not registry authority. |
| `display_name`, `platform`, `architecture`, `client_version` | Bounded descriptive metadata, never identity selectors. |
| `first_seen_at`, `last_seen_at` | Hub/PostgreSQL instants (`timestamptz`), serialized with a time-zone offset. |

The same node keeps its workstation ID across IP/name/key/version changes and
sequential ACP sessions. A distinct node gets a distinct workstation ID even
when it supplies identical metadata or proves the same copied installation key.
No hostname deduplication or physical-device inference is attempted.

`connection` contains session ID, workstation ID, edge-instance ID and expiry.
It is an ephemeral presence lease, not durable Task execution state. A record is
ONLINE while any accepted connection has an unexpired lease; otherwise OFFLINE.
Both states retain durable identity. A 15-second heartbeat rechecks socket identity,
requires a WebSocket ping response and refreshes the 45-second lease. Normal
disconnect removes only that session's lease. Abrupt loss can remain ONLINE until
detection/lease expiry; ONLINE is not a capability or future-liveness guarantee.
Inventory reads never refresh presence or last seen.

The personal Hub has one writer edge. A PostgreSQL session advisory lock prevents
a second instance from clearing live routes. Writer startup clears old connection
leases after acquiring the lock; it never deletes workstation inventory. Lost
storage/schema fails startup or handshake closed. A storage failure during a
heartbeat terminates the affected connection rather than claiming fresh presence.
No in-memory/file fallback can assign an alternate identity.

## Handshake extension and compatibility

The private endpoint, WebSocket subprotocol, binary framing, transport pins,
installation key proof, cancellation and ACP protocol remain unchanged.
New clients negotiate Blaine protocol **2**, adding descriptive platform,
architecture and optional display name to the signed Hello transcript. The Hub
challenge advertises `registration: automatic`. Only after valid client proof does
the Hub transactionally upsert by authenticated node and attach the session.
Ready includes the server-assigned `workstation_id` and a domain-separated server
signature bound to the full handshake and fresh session. A changed/replayed receipt
fails closed. The host session and ACP adapter environment carry the resulting ID
as a future routing hook, without exposing capabilities.

The client retains its existing private `direct-v1` state directory and installation
key. Protocol-1 profile upgrade preserves all deployment/node/key pins. A separate
private `registration.json` caches the verified result; it is not the authoritative
database and `doctor` never registers or probes presence by reading it.

Public alpha.3 uses protocol 1 and remains compatible: the Hub auto-registers it,
but returns the exact historical challenge/Ready shape. Its old `not-implemented`
registration text and key-derived `workstation_id` are legacy client diagnostics,
**not** inventory evidence. Such a client does not receive the new receipt or send
platform/architecture. The Hub uses available WhoIs descriptive metadata and
leaves absent fields empty rather than inventing them. Protocol-2 client live
receipt/metadata evidence must be reported separately from alpha.3 compatibility.

## Operator visibility and deployment

After the explicit schema migration and edge deployment:

```sh
~/.local/share/blaine/transport/bin/blaine-hub-transport \
  --config ~/.config/blaine/services/transport.json workstation list
~/.local/share/blaine/transport/bin/blaine-hub-transport \
  --config ~/.config/blaine/services/transport.json workstation inspect WORKSTATION_ID
```

These bounded, host-local reads report safe JSON, including platform, architecture,
version, presence, last seen and stable node reference. They require no workstation
SSH onboarding, enrollment or approval. Listing is bounded to 1,000 records; exceeding
that personal-deployment bound fails explicitly rather than silently truncating.

`infra/services/workstation-registry-init.py` performs the one-time logical
database/schema setup using the existing PostgreSQL administrator access. It does
not run at client connection time. `transport-stage.py --adopt-registry-dsn ...`
explicitly migrates the previous temporary node allowlist to `tailscale-policy`
admission, retaining the pinned Hub key and persistent user service. Only that
edge service restarts; Restate and the durable runtime remain independent.

Structured `workstation` created/reconnected/disconnected events carry session and
stable inventory references. A creation/reconnection event also records successful
connection; correlate later disconnection by session. No keys, tokens, auth URLs,
prompts, project paths or tsnet state are logged.

## Acceptance boundaries

Required deterministic tests cover unique registration, concurrent retries, new
ACP sessions, stale disconnect, lease expiry, storage reload, changed IP/name,
distinct transport identities with matching metadata/key, invalid storage, signed
receipt substitution and unchanged ACP authority denial. PostgreSQL tests use a
disposable Unix-socket-only cluster, never production tables.

Primary live acceptance uses the designated Mac: auto-registration, read-only
inventory, IDE close/reopen, sequential sessions and restart of only the edge.
Distinct-node isolation uses a safely authorized alternate identity; no primary
state destruction or Tailscale cryptography/revocation test is required. Record
fixture versus live evidence separately. Workstation reboot/upgrade proof is
scoped to what is actually observed. Full second Windows/WSL IDE acceptance remains
E0.F. No configOptions, workspace authority, power management or Task lifecycle
changes belong to this slice.

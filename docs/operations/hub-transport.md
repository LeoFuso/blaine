# Persistent private Hub transport

The edge uses the existing non-root, linger-enabled user systemd manager, alongside
the accepted runtime services. It owns only ACP child processes; stopping or
restarting it cannot stop Restate, the runtime or durable Tasks. Tailscale SSH is
administrative only. The private listener remains the verified Hub address on TCP
7443, with the existing application key and exact peer allowlist.

Repository-owned files:

- [User unit](../../infra/systemd/user/blaine-hub-transport.service).
- [Staging helper](../../infra/services/transport-stage.py), following the existing
  `~/.config/blaine/services` and `~/.local/share/blaine` service conventions.

The staging helper explicitly adopts the candidate's existing private Hub key;
it never generates/rotates a key or copies runtime credentials/state. Private
runtime configuration stays at its existing deployed path. The immutable host ACP
snapshot is exported from an exact Git commit into `transport/releases/<commit>`;
the running edge does not depend on a feature worktree. Repeating identical staging
is idempotent. Source drift, policy drift, redirected/private-key paths, a changed
existing key or a changed binary for an existing release fail closed.

Build the host executable from the exact clean committed `client/` and `runtime/`
source using the pinned Go toolchain, without a network dependency download:

```sh
git rev-parse HEAD
cd client
GOTOOLCHAIN=local GOPROXY=off CGO_ENABLED=0 go build -trimpath -buildvcs=false \
  -o ../.local/hub-release/blaine-hub-transport ./cmd/blaine-hub-transport
cd ..
python3 infra/services/transport-stage.py --repository "$PWD" \
  --binary "$PWD/.local/hub-release/blaine-hub-transport" \
  --candidate-config "$PWD/.local/e0c-direct/host.json" --commit EXACT_COMMIT
```

Run as the established service owner, without sudo. Staging prints only source and
binary digests and does not control services. Confirm `loginctl show-user "$USER"
-p Linger` reports `yes`; do not change host policy or create a root daemon here.
Validate the staged unit, then cut over only the edge while no acceptance ACP
session is active:

```sh
systemd-analyze --user verify "$HOME/.config/systemd/user/blaine-hub-transport.service"
systemctl --user daemon-reload
systemctl --user stop blaine-e0c-direct-candidate.service
systemctl --user enable --now blaine-hub-transport.service
systemctl --user show blaine-hub-transport.service \
  -p ActiveState -p SubState -p UnitFileState -p Transient -p RuntimeMaxUSec
```

The accepted state is active/running, enabled, non-transient and without a runtime
expiry. Validate the private listener, fresh dependency readiness and a designated
Mac round trip. Restart only this edge once and verify its recovery, unchanged key,
unchanged durable service identities and unchanged controlled Task state. Enabled
unit plus existing linger establishes boot configuration; do not claim an actual
host reboot was performed unless separately measured.

If cutover fails, stop/disable the new edge before restoring the previous reviewed
edge invocation. Never run two listeners or restart the runtime/Restate to conceal
an edge failure. Preserve the existing key and Task state. Full workstation
registration/re-enrollment remains E0.D; full second-workstation IDE acceptance is
E0.F.

## Measured deployment and narrow policy

On 2026-09-23, commit `c0e323b39e5287eab4f28898c0da9b14848090b3` was
staged twice with identical receipt and adopted Hub key. The canonical service is
enabled, non-transient, active/running, with `RuntimeMaxUSec=infinity`; existing
user linger remains enabled. An explicit edge restart preserved runtime/Restate
PIDs and the controlled WAITING Task. No host reboot was performed.

The [applied policy](../../experiments/personal-agent-hub/e0c-direct/applied-tailnet-policy.json)
restricts the IPv4 and IPv6 addresses of the two measured Blaine application
installations to the Hub's TCP 7443. It subtracts those exact sources from the
previous broad grant, rather than adding an ineffective narrow grant beside it.
The complement uses four /1 prefixes covering all IPv4/IPv6 space; the policy
validator rejects /0 and wildcard elements inside an IP set. No other existing
source is excluded. The human machine nodes are distinct from the application
nodes, and the existing SSH check policy is unchanged.

Ten policy assertions passed at save, followed by a fresh saved-policy read and
[effective Hub packet-filter verification](../../experiments/personal-agent-hub/e0c-direct/effective-tailnet-policy.json).
Detailed host route inspection showed only each node's own host routes and no
advertised subnet/exit routes in the observed map. The first automatic approval
review blocked saving until the source-set semantics and observed route scope
were checked; the subsequent reviewed update succeeded. Invalid syntax and
cross-family test drafts were rejected without changing the active policy.

This is an exact-installation policy, not automated enrollment or a universal rule
for every future Blaine installation. A changed/reassigned address requires review
against the stable node ID and application identity before policy update. E0.D owns
that registration/re-enrollment lifecycle. Hub admission still independently checks
stable node/principal identity and the signed Blaine handshake. Tags remain an
available future deployment choice, not a capability advertised by this client.

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

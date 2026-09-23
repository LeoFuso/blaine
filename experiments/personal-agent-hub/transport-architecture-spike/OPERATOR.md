# Operator experiments — not a client release

Use only the designated Mac and ST00251 Ubuntu WSL2. These are private experiment
artifacts, not an upgrade to the installed `blaine` client. No PATH changes or
system daemon installation. Builds are locally verified, not an Actions release.

Download/extract the matching archive from the provided local artifact directory.
On the Mac use darwin-arm64; in ST00251 Ubuntu WSL2 use linux-amd64. From the extracted
folder run:

```bash
bash run-spike.sh
```

The script verifies the binary SHA-256 before execution. It runs the probe twice,
second from a different executable directory, while preserving the same explicit
state directory. The first enrollment opens a browser to Tailscale. Complete normal
login to the expected tailnet; do not paste the URL. Device approval may be required.
The second run must report `node_reused: true` and the same node_id. Authentication
is bounded to four minutes per run. It needs the private host fixture running.

Only return `reports/first.json` and `reports/relocated-repeat.json`. Do not upload
`BlaineArchitectureSpike/tsnet` state. It contains private node credentials. Do not
copy it between machines or into a Git checkout. Mock auth state is separate.

After first connectivity succeeds, coordinate a reboot and rerun (without deleting
state), a second-version fixture build, controlled revocation of only the spike
node, and a restricted-ACL test. Those are separate measurements, not assumed from
API documentation. Do not log out the system Tailscale device or alter its policy.

For WSL, the probe does not call Windows Tailscale or a system Tailscale socket.
Windows browser opening uses PowerShell if available; browser fallback displays the
URL locally. A successful run while Windows Tailscale is connected demonstrates
coexistence, not full independence. Coordinate a controlled Windows disconnect and
repeat before claiming independence; do not disrupt the operator's active access.

## Private host fixture

The coordinator runs the Linux binary on the canonical host:

```bash
./blaine-spike-linux-amd64 serve --bind 100.94.139.5:49173
```

This binds only the private Tailscale IP, checks the host node ID, authenticates
actual request socket addresses with the local Tailscale API and restricts them to
the host owner's untagged user identity. It is an echo-only fixture with no Task or
workspace access. It exits after 20 minutes or Ctrl+C. No public listener, SSH
change, ACL change, autostart or persistent service installation occurs.

## ACP browser fixture (separate from real Tailscale enrollment)

JetBrains custom ACP configuration can launch the downloaded probe. Add a separate
`Blaine Architecture Fixture` entry to existing `~/.jetbrains/acp.json`, preserving
all other entries/settings. Replace the command below with the absolute path of the
binary. Explicitly disable both MCP sources for this fixture; do not grant tools.

```json
{
  "agent_servers": {
    "Blaine Architecture Fixture": {
      "command": "/absolute/path/to/blaine-spike-darwin-arm64",
      "args": ["acp-mock"]
    }
  }
}
```

Use the installed IDE's supported controls to disable MCP exposure for this
fixture. If it cannot do that separately, record the limitation before changing
shared settings. The fixture rejects nonempty MCP descriptors regardless. This manual fixture launch
proves no registry provisioning. No verified ordinary-IDE private registry override
was found. Do not overwrite the full config with this example.

Select the fixture, trigger a session and record whether the IDE presents the auth
method. Complete the explicitly labeled **mock** browser confirmation. Confirm a
subsequent session/prompt works, restart the agent to check marker reuse, and use
logout if offered. Observe actual initialize capabilities, not guessed UI support.
No password, real OAuth provider, model or workspace access exists in this fixture.
Remove only its agent entry afterward. Removing the separate mock marker is safe;
removing tsnet credentials is a different lifecycle operation.

## Provisioning result constraint

The registry schema experiment proves native-binary packaging feasibility, including
current alpha-channel restrictions. Without public registration or a verified
private-registry deployment facility, IDE-managed download of Blaine remains
PENDING. An IDE launching a manually downloaded fixture must not be counted as a
provisioning PASS. Record actual IDE/plugin versions and cache path during testing.

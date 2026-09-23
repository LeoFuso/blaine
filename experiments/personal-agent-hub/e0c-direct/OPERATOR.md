# E0.C direct transport candidate — not a release

Use only the designated Mac and Ubuntu WSL2 installation. Keep system Tailscale in
the agreed test state. This client uses embedded tsnet; it does not invoke a system
Tailscale CLI or connect to its daemon. Its credentials belong in the native user
state directory, never in the download folder or a shared Windows mount.

Extract the archive and run `bash accept.sh` in that directory. The script verifies
checksums, preserves the prior executable once, installs the candidate at
`~/.local/bin/blaine`, runs read-only doctor and performs two independent direct
connections, then opens real ACP sessions and tests SIGINT/SIGTERM exit 130.
Normal close preserves identity. Browser login is expected for this
new product installation; the experimental spike identity is not silently imported.

The repository script now creates its report directory and signal-test FIFOs under
the native user home, independently of the download location, and checks FIFO support
before connecting. Earlier candidate packages used the extraction directory; for
those packages, copy the four package files to a fresh directory under the Linux home
before running in WSL. This preserves the package checksums and installation identity.
The measured `mkfifo: File exists` stop under `/mnt/c` occurred before signal tests;
it is not evidence of an ACP signal failure.

On first enrollment, the host may return `TRANSPORT_DENIED`. Send the generated
report containing the public `node_id` and `workstation_id`; the host operator will
add only the verified designated node to its transport allowlist. Rerun the same
script afterward. This temporary deployment review is not E0.D registration.
Never send the private `direct-v1` directory, keys, tsnet state or authentication URL.

macOS: this local alpha candidate is unsigned/unnotarized. If Gatekeeper blocks it,
verify the supplied digest and use the per-application system approval already
used for the spike. Do not disable Gatekeeper globally.

## Real JetBrains launch — after the transport batch

Use the installed stable AI Assistant's custom ACP agent mechanism. Preserve every
existing `agent_servers` entry in its `acp.json`; add only `Blaine E0.C candidate`.
Disable IDE MCP exposure for this test. Blaine rejects nonempty MCP descriptors and
advertises no workstation file/terminal capability. Do not point at a real work
project to test effects: there are no E1/E2 capabilities in this candidate.

macOS command entry (use the actual absolute home path):

```json
"Blaine E0.C candidate": {
  "command": "/Users/leonardo.nuzzo/.local/bin/blaine",
  "args": ["acp"]
}
```

Windows IntelliJ opening the WSL project: the Windows IDE launches `wsl.exe`, which
executes the Linux binary directly. The existing operator topology is preserved;
this is a validation candidate, not a claim that JetBrains WSL behavior is proven.

```json
"Blaine E0.C candidate": {
  "command": "C:\\Windows\\System32\\wsl.exe",
  "args": ["--distribution", "Ubuntu", "--exec", "/home/leonardonuzzo/.local/bin/blaine", "acp"]
}
```

Record the actual IntelliJ/AI Assistant versions, whether Blaine is listed,
launch/authentication UI, and whether a session opens. The Linux client version
must appear as `linux/amd64` in WSL, the Mac as `darwin/arm64`. Never infer process
location from the project path. Do not replace this with Remote Development.
Do not run another Blaine process while the agent holds the installation lease.
Concurrent processes fail `INSTANCE_BUSY`, preventing accidental duplicate nodes.

A safe initial prompt is `inspect e0c-unavailable-probe`. It should return the
runtime's unavailable Task observation; this does not create a Task or access the
workspace. The host operator separately observes the controlled durable acceptance
Task before and after you stop the ACP agent. Do not send coding prompts.

## Explicit logout/reset (only during the coordinated lifecycle test)

Close the IDE agent first. `blaine disconnect --logout` logs out the embedded node,
retaining the application identity and state for inspection. It does not stop
system Tailscale, delete durable Tasks, or promise immediate administrative node
removal. `blaine disconnect --logout --reset-identity` additionally deletes this
installation's identity/store only after a confirmed local logout; a later connect
creates a new identity and requires renewed host authorization. Do not use reset
as a repair for connectivity. The old node may still need administrative removal.

Normal restarts, reboot and binary upgrades must reuse state; no logout/reset is
part of `accept.sh`. Remote revocation propagation and post-reboot reuse require
explicit live observations before being reported as proved.

# Primary macOS fixture evidence

Date: 2026-09-23. This is an architecture experiment, not production E0.C acceptance.

The designated operator-run peer is the arm64 Mac previously identified as
`leonardos-macbook-pro.tail0f2ece.ts.net`. No unattended access to that workstation
was used. Its new embedded node must be distinguished from its system Tailscale
node.

The operator confirmed that `shasum -a 256 blaine-spike-darwin-arm64` matched:

```text
aaca8980bfbf6aeddecc61a162678e1c37af1b8d68306be2bb81a7c262fb0ece
```

macOS initially blocked the downloaded executable with the message that Apple
could not verify it was free of malware. This artifact has no Developer ID
signature/notarization. The warning was a verification warning, not an explicit
malware-detection report. After checksum confirmation, the operator was directed
to the per-executable Privacy & Security exception; no global Gatekeeper change
or quarantine-removal command was prescribed. Checksum agreement proves artifact
integrity against the prepared file, not malware absence. Distribution signing
and notarization remain a product-delivery consideration; IDE provisioning must
not be assumed to remove it.

The operator subsequently reported `status: PASS fixture`. Independently, the
private host fixture recorded these transport-authenticated peer observations:

```text
2026/09/23 11:14:35 fixture peer_node=nmUtVa2GmA11CNTRL route=/stream
2026/09/23 11:14:36 fixture peer_node=nmUtVa2GmA11CNTRL route=/closed
2026/09/23 11:14:36 fixture peer_node=nmUtVa2GmA11CNTRL route=/stream
2026/09/23 11:14:37 fixture peer_node=nmUtVa2GmA11CNTRL route=/closed
```

The listener was bound only to `100.94.139.5:49173`, with the existing owner
WhoIs check and a 20-minute lifetime. Peer IDs above came from host-side WhoIs
on the actual remote socket, not a client-provided header. Association of this
new node with the designated physical Mac currently includes the operator's
execution report; the complete sanitized client report has not yet been received.

In the tested source, PASS is emitted after destination node verification,
binary stream checks, cancellation/deadline/disconnect checks and successful
tsnet close. The short operator report is evidence of that reported outcome;
individual JSON fields and repeat-launch reuse remain to be collected.

The scripted relocated-run report was initially empty; no cause was established.
The operator then ran `./relocated-bin/probe tsnet` directly and explicitly
reported `node_reused: true` and `clean_close: true`. Independently, the host
recorded both stream/disconnect-check pairs at 11:18:00–11:18:02 from the same
stable node ID `nmUtVa2GmA11CNTRL`. This proves reuse across separate process
launches and executable relocation on the designated Mac, with a clean close
reported by the client. It is not a reboot or actual binary-version upgrade test.
The direct-run result was reported from terminal output; the empty scripted JSON
file is not treated as captured evidence.

For the next controlled test, the operator was instructed to disconnect (not
log out of) the system macOS Tailscale application and run the same probe. The
reported result was `STOP private fixture unreachable; inspect service/ACL
independently of login`. This code path follows successful embedded `Up` and
tailnet-context validation, but precedes destination identity and stream checks.
At 14:21 UTC the host fixture process remained running, a local TCP connection
to its private port succeeded, and host Tailscale reported Running, online and
zero health warnings. The experimental peer was offline when checked after the
probe had exited; that observation alone does not explain the failed dial.
System-Tailscale independence was therefore unproved at this point. The initial
probe suppresses the underlying
dial error, so this result cannot yet distinguish DNS, routing, policy or other
connectivity causes. No architecture conclusion or policy change follows from it.

The operator reconnected system Tailscale and repeated the same original probe:
`PASS_FIXTURE`, `node_reused: true`, `clean_close: true`. Host logs corroborated
stream/disconnect-check pairs at 11:22:28–11:22:30 from `nmUtVa2GmA11CNTRL`.
This connected/disconnected/reconnected comparison is evidence of an unresolved
environmental dependency or transient condition, not proof of its mechanism.

The operator subsequently disconnected and quit the macOS Tailscale application,
then reported four original-probe runs in this order: STOP, PASS, STOP, PASS.
This demonstrates intermittent success with the GUI quit; it contradicts a
simple claim that the application must remain connected for every successful
run. It does not establish round-robin DNS, an address-family cause or complete
absence of a residual system network extension. No system service was removed.
The host fixture remained running and independently observed further successful
stream/disconnect-check groups at 11:28:38–11:28:40, 11:28:51–11:28:53 and
11:29:40–11:29:43, all from `nmUtVa2GmA11CNTRL`. These host observations are not
assigned one-to-one to operator invocations without corresponding client reports.
Reliability and the failure layer remain unresolved; repeated eventual success
must not be substituted for readiness or hidden behind automatic retries.

A second isolated fixture revision adds `tsnet --diagnose`. It independently
attempts the canonical MagicDNS endpoint and observed Hub IPv4 with bounded
timeouts, checks the same expected Hub identity after successful connections,
and reports whether the embedded peer map contains that Hub. It emits categorized
DNS/network errors rather than raw backend logs. An IP success never converts a
hostname failure into stream acceptance. `DIAGNOSTIC_ONLY` is not PASS.
The existing node-state path is unchanged. Original artifacts remain available.
Revision checksums and four-target builds are in [diagnostic-builds.json](diagnostic-builds.json).
Formatting, `go vet` and race tests (stream/auth/deadline/error redaction) passed.
No production adapter, published release, ACL or canonical architecture changed.

The operator supplied both complete revision-2 JSON reports, retained in
[macos-diagnostic-reports.json](macos-diagnostic-reports.json). Both had the same
stable node ID, `node_reused: true`, `clean_close: true`, backend Running and zero
health warnings. The first snapshot lacked the Hub: MagicDNS returned not-found
in 174 ms and a direct-IP connection timed out after 12,001 ms. The second
snapshot contained the expected Hub: name and IP connected in 29 ms and 9 ms,
respectively, and both WhoIs checks verified the expected Hub identity. No
application payload/handshake was attempted by diagnostic mode.

This also verifies identity reuse across the actual source/binary change from
the original probe to diagnostic revision 2; it is not a published-client
upgrade or reboot test. It does not prove that the map recovered within a failed
process: revision 2 took only an initial peer snapshot, and its two endpoint
attempts were sequential. The host's absence from that snapshot is measured;
why it was absent and for how long remain unknown.

The pinned `tsnet.Server.Up` waits for Running, fetches status, and requires a
local Tailscale IP. It does not assert a particular peer's presence/readiness.
The resolver first checks the embedded MagicDNS map and may otherwise use the
system resolver. Sources: [Up and Dial](https://github.com/tailscale/tailscale/blob/v1.102.4/tsnet/tsnet.go),
[dial resolution](https://github.com/tailscale/tailscale/blob/v1.102.4/net/tsdial/tsdial.go).
A delayed map is a hypothesis, not an established upstream defect. Revision 3
adds a fixed 20-second same-process status observation followed by one name/IP
comparison. The operator wrapper records three separate measurements and retains
all outcomes; it does not retry until success or change production readiness.

The operator supplied three complete revision-3 reports, retained in
[macos-peer-observation-reports.json](macos-peer-observation-reports.json).
In runs 1 and 3, the Hub was absent in the initial snapshot and present at
3,018 ms and 3,019 ms respectively. Run 2 had it in the initial snapshot. All
retained it through the last sample near 19 seconds, with Running and zero
health warnings. This establishes delayed target-peer visibility within the
same process for two runs, rather than merely a correlation between separate
processes. All three reused the same node across another source/binary revision
and reported clean close.

All six TCP attempts then failed in 4–30 ms with the deliberately limited
`network_operation` classification. At the coordinator's follow-up at
15:07:14 UTC, the 20-minute host fixture had exited normally and its private
port returned connection refused (errno 111); host Tailscale remained Running,
online, with zero health warnings. Client reports contain no wall-clock start
timestamps, so exact listener state at each attempt cannot be reconstructed.
The expired fixture confounds TCP interpretation. These failures do not establish
a tsnet inability to reach a ready listener. The peer-map timing measurements
remain valid independently of the listener. A repeat against a refreshed host
fixture is required before evaluating connectivity after the observation window.

After the host fixture restart, the operator repeated the same revision-3
script and supplied all three terminal reports plus their matching file contents.
These are three runs, not six. The reports are retained in
[macos-peer-observation-repeat.json](macos-peer-observation-repeat.json).
All three name/IP TCP comparisons passed and verified the expected Hub identity:
32/9 ms, 8/4 ms, and 14/4 ms respectively. All reused `nmUtVa2GmA11CNTRL` and
closed cleanly. In run 2 the Hub was initially absent and appeared at 3,018 ms;
it was present initially in runs 1 and 3. Each measurement observed for 20 seconds
before making its single name/IP comparison. The system GUI remained in the
operator-reported disconnected/quit condition; complete removal of residual
system components was not measured.

This proves usable embedded-node TCP connectivity and destination identity
verification in that condition, with repeated delayed-peer visibility measured.
It does not prove an immediate post-Up dial is reliable, that a fixed 20-second
delay is an appropriate product design, or that any status guarantees future
reachability. If adopted, readiness must distinguish enrollment/backend state,
target availability and application handshake, retain bounded cancellation, and
fail closed when the expected target never becomes available. No such production
change was implemented. These diagnostic runs did not carry ACP or application
stream payloads; earlier stream evidence remains separately scoped.

Pending: original stream JSON capture, browser enrollment
observations, actual reboot/published-client upgrade, reliable system-Tailscale-off independence,
revocation, scoped ACL denial and WSL repetition. No production Blaine handshake,
ACP session, workstation registration or durable Task continuity was proved.

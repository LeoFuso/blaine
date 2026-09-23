# One coordinated acceptance batch after the transport decision

Status: proposed test organization, not a new milestone or accepted architecture.
No further incremental workstation download is requested for this spike.

## What can be relied on for the decision

Official released APIs/documentation establish native ACP binary distribution,
agent-owned authentication, userspace tsnet, persistent state, tailnet policy and
revocation mechanisms. Those are documented design capabilities. They need not
each trigger a separate operator experiment just to compare architectures.

Actual evidence already includes Mac private binary-stream fixture success,
Mac/WSL Hub TCP and identity checks, first WSL interactive enrollment, stable
node IDs across processes, Mac identity reuse across binary changes, delayed
peer-map arrival and clean close. Unit/fixture tests cover mock ACP auth,
stream/cancellation/disconnect, bounded target readiness and identity rejection.

These results do not certify the production client, IDE provisioning/auth UI,
WSL binary streaming, revocation, restricted ACLs or server Task continuity.
Documentation-supported expectations must remain labeled as such.

## One downloadable build, one invocation per designated platform

After the operator chooses the transport, prepare the complete test set first,
run local regressions and freeze a source/checksum manifest. Use the repository's
artifact distribution conventions; do not publish a release without authorization.
One versioned package per platform should contain every applicable probe and an
entrypoint that produces one sanitized report. Reuse the same downloaded package
for restart/reboot checks; do not rebuild for a new hypothesis unless a defect
actually prevents the agreed batch.

The host fixture must be started for an agreed bounded test window and report
listener readiness and expiry explicitly. Record UTC timestamps on both sides.
Check host availability before interpreting a client failure. An expired test
listener is a fixture failure, not a reason to change transport or tailnet policy.

Automate the following sequentially in that single invocation:

1. Verify artifact integrity/platform, actual prerequisite/service observations,
   credential directory location/permissions and absence of unintended credentials
   in reports. Do not print or upload private node state.
2. Start the selected transport; present one normal browser authentication action
   when needed. Distinguish local authentication from expected-Hub availability.
3. Wait for the expected target within a deadline, verify transport identity, then
   exercise the selected Blaine handshake and protocol mismatch rejection. A
   production handshake requires the approved host implementation, not an echo
   fixture labeled as Blaine.
4. Exercise binary duplex traffic, bounded buffers, cancellation/deadlines,
   disconnect observation and fresh reconnect with identity revalidation. Check
   both expected success and explicit failure paths without retry-until-PASS.
5. Launch a second process with the same installation state; compare actual node
   identity and record clean exit. Keep subprocess, IDE session and Task identities
   distinct. Test the chosen multi-IDE ownership model once it has been decided.
6. Collect one JSON report with separate PASS/FAIL/NOT_RUN outcomes and enough
   stage timing to diagnose a failure without another custom build.

This is a proposed consolidation of existing acceptance properties. It is not an
implemented runner and does not pull E0.D registration or E1/E2 tools forward.

## Human checkpoints that cannot be honestly automated away

Bundle the real IDE select/authenticate/prompt observation into one brief session,
with the installed IDE/plugin versions recorded. Registry-managed download is a
separate property from launching a manually installed custom agent. Resolve the
binary alpha-version registry restriction without relabeling an alpha as stable.
The generic JetBrains guide warns about WSL; its support clarification distinguishes
a Windows IDE backend from a Linux backend inside WSL via Remote Development.
Record the actual backend OS and launched executable as part of this same IDE
session. Do not treat Linux client connectivity as proof that a Windows backend
can launch that Linux binary, or treat the generic warning as an ACP protocol
incompatibility. Reuse the existing ACP integration mechanism; no custom plugin
or new native Windows client is selected by this test plan.

A reboot, a specifically scoped revocation and a reviewed narrow ACL require
operator/admin action. Plan them as optional coordinated checkpoints for this
decision-support stage and required gates before the corresponding production
claims. Use only the designated installation's node; do not revoke the system
device, weaken broad policy, delete another peer or collect auth URLs. A revoked
installation must fail closed. Successful re-enrollment is a separate observation.

Node inventory currently includes Mac `nmUtVa2GmA11CNTRL` and WSL
`nPsdWribvG11CNTRL`. Preserve their protected state for planned reuse tests.
At retirement, explicitly remove only these experiment nodes and their local
experiment credentials after confirming they are no longer needed. Closing the
fixture or deleting its downloaded executable does not remove a tailnet node.

## Decision stop

Do not execute this follow-up as an implicit transport choice. Keep ADR 0022,
the accepted E0 sequence, production code and the released alpha unchanged until
the operator chooses. The next canonical slice remains E0.C, not registration.

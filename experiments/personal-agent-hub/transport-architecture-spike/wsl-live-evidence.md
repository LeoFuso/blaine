# Designated Windows + WSL2 fixture evidence

Date: 2026-09-23. Peer: ST00251, Ubuntu WSL2, linux/amd64. This is the authorized
additional workstation, not another physical peer. No nested tailscaled or Linux
Tailscale CLI was installed. The executable was downloaded and invoked from a
Windows-mounted Downloads directory; the code uses a separate user configuration
directory for private node state, never the executable's current directory.

The operator was instructed to disconnect and quit the Windows Tailscale GUI
before this test, keeping ordinary internet connectivity. These runs follow that
instruction; the Windows background service's actual state was not measured.
No claim of complete system-component removal follows from quitting the GUI.

The revision-3 checksum check passed. The first run emitted the browser-login
message and reached Running. The next two did not emit a login message. The
fixture uses Windows interop only to open the browser, not for Tailscale CLI,
DNS queries or data forwarding. Complete supplied reports are retained in
[wsl-peer-observation-reports.json](wsl-peer-observation-reports.json); repeated
`cat` output confirms the same three reports and is not additional execution.

All three runs verified the expected Hub identity after TCP connections by both
MagicDNS and observed IPv4. Durations were 16/1 ms, 4/1 ms and 1/0 ms (rounded to
integer milliseconds). All reported clean close, Running and zero health warnings.
The Hub was absent initially in run 2 and appeared at 2,001 ms in the same process;
it was present initially in runs 1 and 3. Each run observed for 20 seconds before
its connection checks. These are TCP/identity tests, not application streams.

All three report the same embedded stable node ID, `nPsdWribvG11CNTRL`, distinct
from the Mac installation. This is positive identity-reuse evidence. The three
`node_reused: false` values expose a measurement defect: diagnostic revisions 2/3
read `observed-node-id`, but only successful stream mode created that reference.
With no prior stream run, an absent reference always yielded false. The reports
are retained unchanged; they do not establish new nodes per launch.

Revision 4 corrects the isolated fixture to create/check the observation baseline
after enrollment in either mode, independently of transport success. This is
non-secret measurement metadata, not node credentials or Blaine registration.
It rejects a changed identity instead of replacing the reference. Stream mode
also waits at most 20 seconds for the expected Hub peer/name in the same embedded
instance, honoring cancellation and rejecting local identity/tailnet changes.
It then performs the existing connection, destination WhoIs and stream checks;
there are no connection retries and no fixed delay before a ready peer is used.
Production code remains untouched. Regression/race tests cover missing peer,
delayed arrival, cancellation, mismatched identity, baseline persistence, stream
and mock authentication. Live revision-4 stream testing remains pending.

Remaining: binary stream/cancellation/disconnect evidence on this workstation,
state-directory/credential protections measured on-device, reboot, revision
upgrade, revocation, constrained ACL denial, and precise background-service
independence. No ACP IDE provisioning, production Blaine handshake, registration,
workspace capability or Task lifecycle result is claimed here.

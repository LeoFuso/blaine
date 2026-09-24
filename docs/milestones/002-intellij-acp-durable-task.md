# Milestone 002 — Interactive Durable Task over ACP

> Historical checkpoint: preserve its successful IntelliJ/WSL/Tailscale SSH run
> and original setup details. Current [Hub design](../personal-agent-hub.md) replaces
> manual transport configuration as the product direction and separately gates
> current IDE/WSL compatibility. This report is not a current onboarding runbook.


Architectural validation spike. Local and IntelliJ validation have both passed.
No LLM is involved.

IntelliJ AI Chat → local SSH client → Tailscale → SSH on Blaine → official Python
ACP agent → loopback Restate → durable `TaskWorkflow`.

## Task and session contract

`runtime/interactive.py` provides the milestone's `TaskWorkflow`. The original
Milestone 001 app remains available separately. A generated `task-<UUID>` is the
Restate workflow key. The task writes RUNNING, journals `summarize-objective`
(word count and SHA-256), writes WAITING_FOR_USER, and awaits the named durable
promise `user-input`. The shared `status` handler can read state during the wait;
`proceed` resolves the promise. The main handler stores COMPLETED with the
operation result and accepted user message. Restate owns state, journal, promise,
and final output; the ACP process stores only temporary ACP session identities.

Commands (plain text, no slash prefix):

```text
create task: Verify an interactive durable task
status task-<returned-id>
continue task-<returned-id>: approved
```

Responses are JSON delivered as ACP agent message chunks. Create polls briefly
for WAITING_FOR_USER; continue polls briefly for COMPLETED. If either returns an
intermediate state, use status. Ending a conversation or cancelling an ACP turn
does not cancel the task. This spike has one approval and no durable cancellation.
No session history restoration is needed: start a fresh session and supply the ID.

Input must be nonblank; IDs accept letters, digits, underscores and hyphens.
Unknown task status is NOT_FOUND (also possible before initialization). Input
for an unknown/nonwaiting task is rejected. The first promise resolution wins;
completed tasks return their original result for repeated continue commands.
An ambiguous create network failure includes the generated ID for recovery.
Retain that ID before retrying; create is not a client-level idempotency API.
Workflow identity and results are subject to Restate retention, not indefinite
archival. No external effects or exactly-once external execution are claimed.

## Host setup and daily commands

Run from the repository root on the Blaine Linux x86_64 host:

```bash
bash scripts/setup.sh
bash scripts/dev-up.sh
bash scripts/doctor.sh                  # scripts/status.sh is an alias
bash scripts/smoke-acp.sh
.local/runtime-venv/bin/python -m unittest discover -s tests -v
bash scripts/dev-down.sh
```

Setup uses installed Python 3.14 and installs dependencies in
`.local/runtime-venv`, with downloads, uv and caches inside `.local`.
Official `agent-client-protocol==0.12.1`, `restate-sdk==1.0.5`,
Hypercorn 0.17.3 and native Restate 1.7.9 are pinned. Transitive versions are
recorded in `.local/runtime-resolved.txt` but are not locked. No global package
installation is performed. Setup requires GitHub/PyPI access.

Dev-up starts both processes, waits up to 45 seconds for readiness, registers the
runtime on first startup, and returns without needing additional terminals.
It refuses occupied ports and partial starts rather than adopting processes.
PID records include boot ID, PID namespace and Linux process start time to guard against PID reuse. A local
flock serializes control operations. Failed starts clean up owned processes.
Dev-down terminates only matching owned PIDs, escalating after a grace period;
it preserves data. Logs and PID records are in `.local/002`. Doctor checks owned
processes, registration and loopback listeners. Do not run setup or change workflow
code while these services are running. Code/schema upgrades of suspended tasks
are outside this spike; deployment registration is not force-updated.

Dedicated Milestone 002 ports avoid the previous spike's occupied default ports:

| Service | Bind address |
| --- | --- |
| Restate ingress | 127.0.0.1:28080 |
| Restate admin/UI | 127.0.0.1:29070 |
| Blaine runtime | 127.0.0.1:29080 |
| Restate fabric | 127.0.0.1:25122 |

Persistence is `.local/002/restate-data`. Inherited RESTATE variables are removed
by dev-up; HTTP calls bypass inherited proxies. No listener is exposed to LAN or
Tailscale. Old Milestone 001 processes are not owned or stopped by these scripts.

`bash scripts/run-acp-agent.sh` launches only the ACP agent. Start dev-up first.
The launcher resolves the repository relative to itself, so a remote client's
working directory is irrelevant. stdout is exclusively newline-delimited ACP;
diagnostics go to stderr. Do not add shell banners or `echo` to this launcher.

## Remote IntelliJ configuration

Prepare Tailscale connectivity and SSH key authentication to the host. From the
client's terminal, connect once normally to verify the host key and authentication.
Use an existing SSH alias (here `blaine-tailnet`) targeting the host's Tailscale
name/address. No port forwarding is required. SSH startup files must not print
to stdout for noninteractive commands. On Blaine, run setup and dev-up before
starting the manual validation below.

Find the **local** SSH executable: PowerShell `(Get-Command ssh).Source` or
`where.exe ssh` on Windows; `command -v ssh` on macOS/Linux. Use the discovered
absolute path in `command`; JSON-escape Windows backslashes as `\\`. Do not
assume a particular Windows installation location. The remote command below
uses the absolute path on Blaine, not a path on the IntelliJ client.

In IntelliJ AI Chat choose **Add Custom Agent**, which opens
`~/.jetbrains/acp.json` (on Windows, under the user's home directory). Merge this
entry with existing agents, substituting the discovered executable and SSH alias:

```json
{
  "agent_servers": {
    "Blaine": {
      "command": "<absolute-local-ssh-executable>",
      "args": [
        "-T",
        "-o", "BatchMode=yes",
        "-o", "ServerAliveInterval=15",
        "-o", "ServerAliveCountMax=3",
        "blaine-tailnet",
        "exec /home/leofuso/workspace/blaine/scripts/run-acp-agent.sh"
      ]
    }
  }
}
```

`-T` disables pseudo-terminal allocation; ACP remains on stdin/stdout.
BatchMode requires working noninteractive key authentication. Keep both
**Pass custom MCP servers** and **Pass IntelliJ MCP server** disabled in the
agent settings; this spike does not use either. There is no agent login, model
selection, or subscription used by Blaine. An IntelliJ/AI Assistant version
supporting custom ACP agents is required; managed installations may restrict them.

## Final MANUAL IntelliJ validation — PASSED

1. Configure the custom Blaine ACP agent above and select it in AI Chat.
2. Send `create task: IntelliJ session independence`; save the returned task ID
   and observe WAITING_FOR_USER.
3. Close/end that ACP conversation.
4. Start a new Blaine conversation/session.
5. Send `status <saved-task-id>`; require WAITING_FOR_USER and the same objective.
6. Send `continue <saved-task-id>: approved from the second IntelliJ session`.
7. Observe COMPLETED and the stored result including that message.

Record the ID and screenshots/transcript under `.local/evidence` if desired.
Manual IntelliJ validation passed on 2026-09-14.

The client was IntelliJ with a project opened through WSL. IntelliJ launched
`/usr/bin/ssh` as the ACP transport, connecting through Tailscale SSH to Blaine
and executing `scripts/run-acp-agent.sh`.

Validation confirmed:

- task creation reached `WAITING_FOR_USER`;
- the Task ID remained stable after ending the original ACP conversation;
- a new IntelliJ ACP session retrieved the same Task and state;
- the new session successfully signalled the Task;
- the Task reached `COMPLETED`.

This establishes the intended session-independence property end-to-end through
IntelliJ, WSL, SSH, ACP, and Restate.

## Local automated evidence

`smoke-acp.sh` uses the official SDK client over real subprocess pipes. It creates
and queries a task, SIGKILLs the first ACP process, starts a new process/session,
recovers the identical waiting state, signals it and retrieves completion. It
also checks unknown IDs, malformed commands and repeated postcompletion input.
Every captured stdout line must be a JSON-RPC 2.0 message. The test has a 90-second
overall timeout and closes its own agents. It leaves runtime services running.

Evidence: `.local/evidence/002-acp/` contains raw stdout, separate stderr,
command/response transcripts, process/session IDs, kill exit code and summary.
For a complete acceptance run that starts and stops its own services:

```bash
.local/runtime-venv/bin/python scripts/verify-interactive.py
```

Run this with Milestone 002 services stopped. It also verifies repeated dev-up,
service restart with the same persisted completed result, and listener cleanup.
This single-process-tree harness works in execution sandboxes that terminate
background processes when a tool invocation ends. For interactive use, run dev-up
from a normal host shell before connecting IntelliJ.

Local validation passed on 2026-09-14: setup, both services, SDK handshake and new
session, stable task identity, WAITING_FOR_USER query, SIGKILL of the first agent,
recovery in a new agent/session, signal, completion and final result retrieval.
Captured stdout contained only ACP messages. Service restart retrieval and owned
listener cleanup also passed. Eleven unit tests cover operation validation,
command handling, error delivery, ambiguous create recovery and process ownership.
The acceptance harness leaves Milestone 002 services stopped and data retained.

Other `002-*` files contain setup, service readiness, tests and lifecycle checks.
Services retain their operational logs in `.local/002/`.

Process failure of Restate/runtime was evaluated separately in Milestone 001;
this milestone's required crash is the ACP process. This is single-host local
persistence, with no power-loss, replication, backup or upgrade guarantees.

## Sources

- [Official ACP Python SDK](https://github.com/agentclientprotocol/python-sdk)
  and its echo-agent example informed the minimal agent implementation.
- [Restate workflow promises](https://docs.restate.dev/develop/python/external-events)
  document durable waits and resolution from shared workflow handlers.
- [JetBrains custom ACP configuration](https://www.jetbrains.com/help/ai-assistant/acp.html)
  documents the agent_servers format and custom-agent setup.

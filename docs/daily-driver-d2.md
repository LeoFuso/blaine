# Daily Driver D2 — Personal Agent / Remote Task Intake

This is the implemented D2 binding/usage guide and its bounded evidence record.
[Personal Agent Hub E0–E3](personal-agent-hub.md) owns the next workstation/client
product design; the [roadmap](roadmap/001-blaine-development-roadmap.md) owns current
sequencing. Historical SSH/worktree launch examples here remain reproduction
instructions, not the future client onboarding contract. Existing Task contracts
remain normative within their documented implementation limits.


D2 exposes the current `CognitiveTaskV1` kernel through a stateless Personal
Agent binding and ACP stdio adapter. It supports small deterministic work,
authoritative inspection, typed human responses, explicit cancellation, and
bounded project reads through an ACP client. There is no new Task runtime.

## Harvest and boundary

| Prior work | Reused evidence or mechanism |
| --- | --- |
| `63d929b`, `8d5a651` | TaskSpec, create/status/signal/result semantics, stateless Personal Agent control plane |
| `869869a` | Tools before model inference; the small Task uses local `text.stats` |
| `a7dc9f2` | Official ACP SDK, JSON messages, Restate workflow identity, independent sessions, process-loss acceptance |
| `ec2f738` | Previously demonstrated IntelliJ → WSL/SSH/Tailscale → ACP → Restate path |
| ADRs 0001, 0003, 0004, 0012 | Task ownership, native durable waits, replaceable transport and worker boundaries |
| Kernel through Increment 12 | PolicyGate, CompletionVerifier (`evaluate`), exact immutable artifacts, HumanDecision contracts, joined child Tasks |

The old `TaskWorkflow`, free-text `proceed`, random identity on every retry,
unconditional human approval, and controller polling are not used in D2. Those
milestone files remain historical experiments. Their old completion logic is not
the current CompletionVerifier. Prior IntelliJ evidence established remote Task
control, not workspace filesystem calls; its MCP forwarding was explicitly off.

```text
trusted human/client
  → ACP adapter (SSH stdio for remote use)
  → PersonalAgent operations / RestateBinding
  → CognitiveTaskV1 durable Task
  → PolicyGate → capability / durable dependency → CompletionVerifier
  → authoritative projection and artifact retrieval through the same adapter
```

`runtime/personal_agent.py` has no ACP objects, session lifecycle, model loop,
database, or Task cache. `runtime/personal_acp.py` holds only ephemeral ACP session
IDs and workspace routing. The same semantic operations can be exposed by a later
transport without changing the Task runtime. D2 adds no MCP server, public API,
Telegram handler, workspace daemon, Context Compiler, or worker-session program.

## Accepted requests and identity

The binding accepts the kernel's existing versioned `TaskSpec`, or a versioned
`TaskRequest` envelope containing `task_spec` and one `initial_action`. The action
uses the existing `INVOKE_CAPABILITY` shape. This is bounded execution input,
not a workflow graph or a duplicate Task DTO. The input is persisted by Restate;
the kernel dispatches it through the same PolicyGate as a cognitive decision.
It does not call cognition to execute an already selected deterministic action.

The existing kernel subset of TaskSpec requires `objective`, exact verifiable
`completion`, and optional `capabilities` and `autonomy.allowed` / `child_tasks`.
The broader conversational [TaskSpec contract](contracts/task-spec.md) remains
intent guidance; D2 rejects unsupported fields rather than silently ignoring
cloud, context, schedule, or approval constraints. There is no cloud adapter in
this deployment. Required capabilities do not grant authority: dispatch requires
both the capability requirement and the allowed authority. Workspace reads are
also restricted to the exact accepted initial operation.

Creation requires a caller-retained `request_id` (1–80 letters, digits, `_`, `-`).
The Task ID is `task-` plus SHA-256 of that ID. Restate's workflow key admits exactly
one main invocation, including concurrent client submissions. Only the caller whose
send Restate admitted (`Accepted`) receives `SUBMITTED`. A retry uses the same
request ID and identical request. Every other create with that ID (retry, replay
or concurrent duplicate) receives `EXISTING` for the admitted Task. If its input
differs, it is rejected, including under concurrency ([#4](https://github.com/LeoFuso/blaine/issues/4)).
If the admitted Task is not inspectable within a bounded wait, the create reports
an uncertain, retryable outcome, never `SUBMITTED`. The receipt `SUBMITTED` is
transport acceptance, not verified Task initialization.
An unknown query is `UNAVAILABLE`, including initialization races; it does not
assert that a submitted request was lost. A timeout preserves the recoverable ID.

Identity/deduplication guarantees apply within the configured seven-day completed
workflow retention, not forever and not after administrative purge. Use a new
request ID for new work. There is one private user's namespace, not multi-tenant
identity management.

## Controls

ACP text conveniences:

```text
summarize my-first-request: a small local input
decision my-decision-request: Continue with the bounded operation?
inspect task-<returned-digest>
result task-<returned-digest>
artifact task-<returned-digest>: answer
respond task-<returned-digest>: YES
cancel task-<returned-digest>
fulfill task-<returned-digest>
```

`summarize` means deterministic word count and input SHA-256, not an LLM summary.
Normalization predicts the accepted output digest; `text.stats` executes the
operation within the durable kernel. `decision` accepts YES/NO through the existing
HumanDecision schema. A NO response completes the *decision-recording* Task; it
does not authorize a separate effect. No approval grants authority implicitly.

`task <JSON>` exposes the transport-neutral control envelope:

| operation | other fields | behavior |
| --- | --- | --- |
| `create` | `request_id`, `task_request` | Submit existing TaskSpec/TaskRequest; return stable identity and receipt |
| `inspect` / `result` | `task_id` | Read current Task state and available verified result, including partial/absent output |
| `artifact` | `task_id`, `name` | Retrieve a Task-admitted artifact with digest reference and bounded UTF-8 content |
| `respond` | `task_id`, `response` | Submit unchanged typed `HumanDecisionResponse` |
| `signal` | `task_id`, `response` | Submit the kernel's existing typed `ExternalInput` |
| `workspace-result` | `task_id`, `response` | Submit a matching typed `CapabilityResult` for a pending authorized read |
| `cancel` | `task_id` | Request native Restate invocation cancellation |

Inspection includes objective, accepted specification/digest, lifecycle, revision,
known blocking dependency, pending HumanDecision or workspace request, child
references, completion evaluation, artifacts, and final TaskResult/concerns.
It reads native workflow state and its referenced artifacts. It omits internal
decision/context contents, promise addresses, and model reasoning. ExecutionEvent
is never a query authority. No list/index store is introduced.

Human requests are published by the authorized `human.request` capability. The
existing workflow automatically suspends on its named promise; cognition does not
choose WAIT. Responses must match Task, request, revision, digest, and allowed
value. Only the consumed response is retained as human evidence. A submission
receipt alone does not claim resumption or completion.

Cancellation uses the stored native invocation ID and `ctx.cancel_invocation`.
`CANCELLATION_REQUESTED` is followed by authoritative inspection; native terminal
409 `cancelled` maps to `CANCELLED` and a retained TaskResult. This is cooperative
cancellation at a durable await, not rollback of completed effects or process
termination. Completion can win a race with cancellation. Already terminal Tasks
return `ALREADY_TERMINAL`. ACP turn cancellation and disconnect never cancel Tasks.
The native mechanism follows [Restate cancellation semantics](https://restate.dev/blog/a-remote-control-for-your-agents).

## ACP / IntelliJ workspace boundary

An explicitly authorized `workspace.read` action accepts an absolute POSIX
`workspace`, a confined relative `path`, and an output `artifact` name. PolicyGate
checks authority and exact accepted action before publishing a WorkspaceReadRequest.
The Task suspends durably awaiting its matching CapabilityResult. No workspace
bytes are read during intake, and no filesystem is copied to Blaine.

`fulfill <task-id>` queries that authorized pending request, checks the active
session's workspace and advertised ACP `fs.readTextFile` capability, and invokes
the official client filesystem method. The client must enforce its own filesystem
permission boundary, including symlink targets. Paths are never resolved against
the Blaine host. D2 supports the earlier POSIX/WSL project direction; native
Windows workspace paths are not yet supported. Results are bounded to 4 KiB,
validated against operation identity, retained immutably, and checked by the
existing exact-digest CompletionVerifier. Arbitrary client-supplied artifact refs
are rejected. A mismatching digest never produces verified completion.

The ACP process may disappear while the Task waits. A new session in the same
workspace can fulfill the same Task. Duplicate read attempts after response loss
are possible; the operation is read-only, and native one-shot promise resolution
prevents replacing accepted evidence. This is an explicit continuation of an
authorized capability, not an IDE-owned Task lifecycle or a remote filesystem daemon.

Automated D2 acceptance uses the real official ACP client/server protocol and a
disposable project fixture. It does **not** claim a new live IntelliJ run. The
prior IntelliJ remote-control mechanism is reused; verifying that the installed
IntelliJ client advertises and permits `fs.readTextFile` remains a workstation check.

## Run privately

Run `bash scripts/setup-runtime.sh` when local dependencies are absent. The pinned
runtime remains Restate 1.7.9 / SDK 1.0.5 / ACP 0.12.1. From the repository root,
start these two commands in separate host terminals:

```bash
.local/bin/restate-server --config-file runtime/personal-restate.toml
bash scripts/run-personal-runtime.sh
```

Register this fresh D2 deployment once, after both processes are ready:

```bash
curl --noproxy '*' --fail http://127.0.0.1:49070/deployments \
  -H 'Content-Type: application/json' \
  -d '{"uri":"http://127.0.0.1:49080"}'
```

Configure the existing IntelliJ ACP custom-agent SSH command from
[Milestone 002](milestones/002-intellij-acp-durable-task.md) to execute
`bash /home/leofuso/workspace/blaine-personal-agent/scripts/run-personal-agent.sh`.
For local SDK clients, launch that script with bash. stdout contains only ACP;
forensic control events go to stderr. Kernel events are `.local/d2/events.jsonl`.
No objectives, raw file contents, credentials, or conversation history enter
those event payloads. Exact evidence stays behind the artifact boundary.

All runtime ports bind loopback (ingress 48080, admin 49070, runtime 49080,
fabric 45122). Existing SSH authentication provides remote access. Do not publish
or proxy these listeners publicly. The binding refuses non-loopback ingress.
The local host and authenticated SSH user are trusted; this is not a multi-user
authorization service. D1 services, data, ports, and worktree are untouched.

Restate data is `.local/d2/restate-data`; artifacts use `.local/d2/artifacts`.
The capability fixture SQLite file is inherited from the existing Capabilities
adapter and is not a Task ledger. Restart the ACP controller freely. Restarting
the same runtime/server version preserves native state and waits. D2 acceptance
uses an isolated fresh deployment: it is not evidence of safe in-place code
upgrades of suspended legacy workflow journals. Do not force-register this
deployment over an active earlier kernel/probe deployment.

## Evidence and limits

Reproduce in a fresh output directory:

```bash
.local/runtime-venv/bin/python -m unittest discover -s tests -v
.local/runtime-venv/bin/python scripts/verify-personal-agent.py \
  --restate-server .local/bin/restate-server --output .local/d2-acceptance-new
git diff --check
```

Retained evidence is [daily-driver-d2](../experiments/daily-driver-d2/evidence/summary.json).
It covers five native Tasks, concurrent/replayed creation, independent sessions,
two controller SIGKILLs, runtime and Restate restart, typed human suspension and
resume, cancellation, remote verified artifacts, policy denial without workspace
access, and one real ACP fixture read. Successful/waiting Tasks have zero cognitive
journal steps. The denied Task's deterministic STOP adapter makes no model call.
Native Task invocation counts and runtime snapshots establish execution state;
events only supplement that evidence. The broader Increment 12 native regression
is retained alongside the repository test report.

Remaining Daily Driver work: live IntelliJ filesystem-capability validation,
normal natural-language investigation/refactor normalization and suitable
completion criteria, broader bounded capability adapters, and host service
deployment when separately authorized. Generic semantic Tasks are not claimed
to execute in this deterministic D2 deployment. Completion contracts remain the
existing exact-artifact/human-response subset. The control surface does not yet
implement constraint modification, scheduling, or Task listing.

The development [TaskSpec draft](daily-driver-d2-request.json) was not submitted:
the session had no configured development-work execution binding. The five
acceptance Tasks are real native submissions and are identified separately in
the evidence. No development lifecycle is reconstructed from chat.

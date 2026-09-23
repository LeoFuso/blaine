# Blaine development roadmap and repository handoff

**Living checkpoint: 2026-09-21. Current program: Daily Driver Enablement / Personal Agent Hub E0–E3.**

This is Blaine's authoritative **living development program**, handoff for future
human/agent sessions, and record of intended sequencing and dependencies. It is
**not a release calendar**, a fixed long-range commitment, or a substitute for
ADRs, contracts, milestone reports, or measured evidence. Dates identify evidence
checkpoints, not promised delivery dates. Read the [current next work](#current-next)
block before selecting an increment.

> The roadmap preserves direction. Evidence chooses the next increment.

> `main` is the latest coherent, safe and truthfully documented state of Blaine, not merely the set of fully completed experiments.

This checkpoint is based on kernel milestones through 037, D1 infrastructure
acceptance (`48b077d`, `e642966`) and its activation runbook (`e2d9134`), and D2
implementation/validation (`d7a492f`, `658fef5`). These are repository evidence,
not a fresh claim about host health. The Hub checkpoint includes the isolated
E0.A client foundation and [E0.B network prerequisite evidence](../../experiments/e0b-tailscale-onboarding/README.md); it does not change
platform acceptance. See the
[documentation authority map](../README.md). A clone supplies the program and
evidence; it does not supply secrets, machine state, or host mutation authority.

## Product destination

Blaine is a **personal-first agentic work system**. Coding is an important
workload alongside investigation, issue tracking, research and personal operations.
Blaine is not merely a coding agent, chat wrapper, generic agent framework, or LLM
session manager. Interactive work is the default; unattended work is a capability.

> Task > session.

The intended Daily Driver lets a user delegate real work: inspect or modify a
codebase through a trusted workstation/IDE; make a small refactor and run tests;
investigate a technical problem; use issue trackers and other reusable
capabilities; perform personal operational Tasks; create and reuse capabilities
under authority; wait for a human decision, notify remotely, and resume the same
Task after a response. Process and host failures must not silently lose Task state.

Local inference is abundant relative to paid frontier intelligence. First use
authoritative tools and deterministic operations when they suffice; use local
cognition when semantic choice is necessary; selectively route frontier work
under explicit authority and context boundaries. Neither local nor paid inference
should simulate a reliable tool or become the lifecycle engine. See the
[local-first policy](../policies/local-first-and-context.md).

## Stable architectural boundaries

These boundaries have kernel evidence within the recorded experimental scopes.
They are constraints on new product work, not a claim that every future workload
or host-disaster scenario has passed.

| Boundary | Ownership and invariant | Evidence / contract |
| --- | --- | --- |
| Task and lifecycle | Task state is durable. Restate owns lifecycle, retries, timers, suspension/resumption and crash recovery. Models, workers, ACP/Personal Agent/chat sessions do not own that lifecycle. | [Task identity ADR](../decisions/0001-task-is-the-unit-of-work.md), [runtime ADR](../decisions/0003-evaluate-restate-as-durable-runtime.md), [kernel progress](../milestones/cognitive-kernel-progress.md) |
| Cognition | Models propose semantic intent; Blaine determines admissible actions; code lowers intent into operational protocol. Cognition selects semantic work to attempt, not whether a known wait or verified completion should occur. | [semantic boundary and verifier-driven progression](../milestones/024-cognitive-kernel-increment-8-passed.md), [architecture checkpoint amendments](../research/cognitive-loop-checkpoint.md) |
| Waiting | Known external dependency → durable runtime suspension. No model call merely to choose WAIT, including human input and joined child outcomes. | [HumanDecision milestone](../milestones/011-cognitive-kernel-increment-5-passed.md), [parallel child Tasks](../milestones/037-cognitive-kernel-increment-12-parallel-children.md) |
| Completion | CompletionContract and deterministic CompletionVerifier own completion. Worker/model claims are insufficient. Parent and child completion remain independent. | [completion policy](../policies/task-completion-and-lifecycle.md), [progression evidence](../milestones/024-cognitive-kernel-increment-8-passed.md), [child evidence](../milestones/037-cognitive-kernel-increment-12-parallel-children.md) |
| Authority | PolicyGate / hard execution authority decides whether a concrete effect may execute. Suitability/economic routing is not authority. Technical capability, authorization, and approval/autonomy are separate. Workers cannot broaden grants. | [frontier contract](../contracts/frontier-dispatch.md), [YouTrack proof](../milestones/012-cognitive-kernel-increment-6-passed.md), [D2 scoped workspace proof](../daily-driver-d2.md) |
| Context | MIRIX is semantic memory, not Task state. Project graphs are derived knowledge, not authority. Chat history is not Task state. Frontier authority binds the exact projected bytes delivered to the worker binding; raw context cannot bypass projection. | [MIRIX milestone](../milestones/009-cognitive-kernel-increment-4-passed.md), [project-knowledge carveout](../milestones/025-cognitive-kernel-increment-9-passed.md), [projection contract](../contracts/frontier-dispatch.md) |
| Workers | Worker dispatch ≠ model inference; worker session ≠ Task; worker completion ≠ Task completion. Hidden worker/provider/model usage stays UNKNOWN when unobservable; do not invent exact call counts, models or costs. | [worker/harness milestone](../milestones/015-cognitive-kernel-increment-7-passed.md), [live frontier proof and accounting limits](../milestones/036-cognitive-kernel-increment-11-live-pass.md) |
| Observability | ExecutionEvent is semantic forensic evidence, never runtime authority. Logical Task causality and physical tracing causality are distinct. Telemetry failure must not determine Task correctness. | [ExecutionEvent contract](../contracts/execution-event.md), [observability proof](../milestones/027-cognitive-kernel-increment-10.md) |

A configured implementation, proposed ADR, isolated proof, live binding proof,
and product acceptance are different claims. Preserve those distinctions when
updating this document. ADR 0018 retains its recorded proposal status; D1 documents
which platform direction and packaging the user subsequently accepted. Do not
silently mark every proposal validated because one implementation slice passed.

## Cognitive Kernel — Increments 1–12

**STATUS: COMPLETE.** [Progress and evidence index](../milestones/cognitive-kernel-progress.md).

The program established a durable per-Task execution loop with bounded real local
model cognition and a JSON-only semantic decision path. It incorporated MIRIX
memory/context, durable typed HumanDecision requests/responses, a YouTrack
capability admitted through PolicyGate, and a replaceable external worker/harness
boundary. The procedure experiments resolved progression ownership: evaluate
completion from evidence and suspend on known dependencies without asking cognition
to reproduce runtime facts. Project-knowledge experiments preserved source truth
and freshness over derived navigation.

ExecutionEvent supplied backend-independent forensic evidence. Increment 11
separated frontier hard authority, economic suitability and accounting; bound
authorization to exact context projection; and passed one fresh, authorized live
Codex dispatch after version-aware Codex 0.155.1 event normalization. That proof does
not establish arbitrary model quality or known provider internals. The earlier
failed live Task and UNKNOWN reservation remain historical facts, not repaired
by the later PASS. See [live closure](../milestones/036-cognitive-kernel-increment-11-live-pass.md).

Increment 12 proved bounded durable parallel child Tasks: explicit relationships,
independent authority/context/completion, stable identities, ALL_TERMINAL joining,
truthful failure propagation, and recovery without duplicate child/effect execution.
The evidence covers 12 native Tasks and zero parent cognition while waiting; it
is not an advanced multi-worker strategy program. See [milestone 037](../milestones/037-cognitive-kernel-increment-12-parallel-children.md).

> The Cognitive Kernel is no longer the primary development bottleneck.

Future kernel changes should answer concrete Daily Driver evidence. Do not reopen
abstract kernel increments or repeat completed experiments merely because a new
session lacks the old conversation. Historical STOP records preserve how the
boundaries were learned; they do not supersede subsequent documented closure.

## Current program — Daily Driver Enablement

The objective is no longer to prove abstract kernel primitives:

> Make Blaine useful for real personal/work Tasks as soon as possible without bypassing the proven boundaries.

**Daily Driver v0** is a product milestone: a long-lived Blaine service accepts
Tasks remotely; operates against a trusted IntelliJ/workstation environment;
inspects and makes small bounded code changes; runs relevant tests/builds; returns
artifacts, diffs and results; waits durably for human input through a remote
channel; resumes the same Task; reuses capabilities; and survives the operational
recovery path actually proven by D1. It is not achieved yet. D7 evaluates this
experience as a whole.

| Workstream | Current status | What it unlocks |
| --- | --- | --- |
| D1 — long-lived platform runtime | **IN PROGRESS — infrastructure foundation PASS** | Stable service ownership and operational recovery |
| D2 — Personal Agent / remote intake | **PASS**, bounded control/fixture scope | Durable work accessible without kernel probes |
| D3 — live IntelliJ / real code Tasks | **PLANNED through E1–E3**, not live-accepted | Useful work in the existing trusted project environment; E0 connection comes first |
| D4 — reusable capability system | **PLANNED** | Reuse without a monolithic Personal Agent integration layer |
| D5 — human interaction channels | **PLANNED** | Notifications and asynchronous remote decisions |
| D6 — operational/cognitive observability | **PARTIALLY IMPLEMENTED / ACCELERATED BY D1** | Diagnose real Tasks using the existing stack |
| D7 — v0 acceptance | **PLANNED** | Evidence that the combined product is a Daily Driver |

### Near-term product sequence — Personal Agent Hub E0–E3

The [canonical Hub design](../personal-agent-hub.md) and
[ADR 0022](../decisions/0022-workstation-personal-agent-client.md) define the next
bounded product architecture. **E0.A is PASS for the isolated client foundation**:
[client/build guide](../../client/README.md), [evidence](../../experiments/e0a-blaine-client/README.md).
**E0.B development-platform PASS; cross-platform PARTIAL** adds real Tailscale
detection, read-only doctor and idempotent network readiness on Ubuntu amd64.
Four standalone builds and install/auth fixtures passed; macOS runtime remains
unverified and WSL host reuse is STOP pending a live spike.
**E0.C PASS** ([migration evidence](../../experiments/personal-agent-hub/e0c-direct/README.md))
now implements the operator-selected embedded tsnet/direct private transport.
Local protocol/identity/process regressions, host readiness and designated Mac/WSL
direct binary/ACP/signal batches passed within their recorded scope. Public alpha.3
plus the host ACP compatibility corrections now has a real Mac IntelliJ read-only
round trip and clean-session-end/Task-independence proof. Effective narrow tailnet
policy and canonical persistent host deployment have now passed, followed by a
repeat primary Mac IDE round trip under that final configuration.
Minimum transport identity reuse has passed; registration/revoke/reset/re-enrollment
belongs to E0.D and full Windows IntelliJ-to-WSL acceptance belongs to E0.F.
Prior SSH and E0.A/B evidence keeps its original scope. E0.D has not started.
Full Blaine onboarding,
remote effects and coding E2E remain unvalidated.
Accepted platform/runtime capabilities are inputs, not a reason to reopen their
entire workstreams. Workstation and worker remain independent.

| Milestone | Status / product outcome | Dependencies and D-series mapping |
| --- | --- | --- |
| E0 — Connect a Workstation | **E0.A foundation PASS; E0.B Linux prerequisite PASS / cross-platform PARTIAL; E0.C PASS; full E0 remains unaccepted.** Small portable client, embedded private connectivity, browser enrollment, handshake/registration, safe IntelliJ config and read-only doctor. Linux/macOS/Windows+WSL2 design; initial live proof may cover fewer platforms explicitly. | Consumes D1 service availability and D2 controls; no workspace mutation. Mac real IDE read-only exchange passed. E0.C narrow tailnet policy and canonical persistent Hub deployment passed. Registration lifecycle belongs to E0.D; full second-peer Windows IDE/WSL acceptance belongs to E0.F. E0.D registration is unblocked, not started. |
| E1 — Remote Workspace Read | **DESIGNED.** Actual second-workstation IntelliJ read, confined paths and evidence in the same durable Task across reconnect. | E0; delivers D3.A product proof. Live client capability/confinement gates remain open. |
| E2 — Remote Workspace Effects | **DESIGNED.** Conditional bounded file write and authorized workstation test/build with deterministic verification. | E1; supplies D3.B effects. Write concurrency/terminal/provider gates must pass; no unrestricted shell fallback. |
| E3 — First Personal Agent Coding E2E | **DESIGNED.** Natural-language request, memory/worker, genuine human response, same-Task resume and verified Java 25 Gradle result. | E2; spans synthetic D3.B proof and prepares D3.C, without claiming useful real-work acceptance or all D7. |

D1 remains platform/runtime work; D2 remains bounded remote intake; D3 remains live
IntelliJ/real code Tasks. Their historical definitions and evidence are unchanged.
E0–E3 are product/E2E gates consuming those capabilities, not renamed D milestones.
Post-v0 Cycle E (advanced multi-worker patterns) is also unchanged.

The selected E0.C path embeds tsnet in the workstation client; no separately
installed workstation CLI/daemon or nested WSL daemon is required. Tailscale
remains private network infrastructure, separate from Blaine application identity
and registration. SSH remains administrative. Windows IntelliJ opening the WSL
project requires live validation of its explicit Linux-client launch boundary.

New platform/observability work is **not on the E0–E3 critical path** without an
observed blocker. Perfect Task-level OTel, Cloud logs/traces, Fleet, telemetry
restart durability (OBS-001), backup continuation and full D1.G acceptance are not
implicit prerequisites. Existing services must be ready for the exercised path;
fix a demonstrated availability/identity/safety blocker narrowly and retain its
evidence. D7 keeps its broader operational acceptance requirements.

### Explicitly not blockers for Daily Driver v0

Blaine does **not** need an advanced Context Compiler, Jev, learned routing,
Graphify/project graph, advanced Worker Sessions, multi-agent critic/debate,
cloud backup, HA, Kubernetes, or a sophisticated custom UI before useful operation.
These may evolve after real usage begins. Pull only a bounded prerequisite forward
when evidence demonstrates that it blocks v0; do not import an entire later cycle.

<a id="d1"></a>
## D1 — Long-Lived Platform Runtime

**STATUS: IN PROGRESS — infrastructure foundation and infrastructure-only rootful
host reboot PASS. Rootless migration: PASS. Backup: PAUSED.**

The [rootless migration checkpoint](../platform-rootless-docker.md) and
[ADR 0020](../decisions/0020-rootless-docker-operator-runtime.md) select user systemd
and linger. Full candidate, coherent offline copy, cutover and controlled restarts passed.
The rootless user stack and linger are enabled; the legacy system owner is disabled.
D1.A/B/C/D live service adoption is now PASS: five enabled user units, 131072-token
Qwen with one generation, concurrent GPU embeddings, Goose/Worker, retained MIRIX
memory, retained Restate Tasks and actual Blaine cognitive/resume evidence.
No benchmark program or hybrid CPU/GPU investigation was introduced.
[Operational evidence and exact reboot procedure](../platform-services.md) preserve
[ADR 0019](../decisions/0019-local-inference-serving-baseline.md).
D1.G host reboot remains pending and D1.F backup remains PAUSED.

**User-visible completion:** after boot, the operator logs in to a ready Blaine
that can recover and continue its existing durable Tasks without manual service
starts. User systemd + linger must start all adopted services independently of
login. Dependency readiness and same-Task recovery are required in addition to
enabled units. See the [current startup gap and acceptance](../platform-d1.md#ready-at-login--configured-and-live-tested-host-reboot-pending).

**Why:** the kernel can be durable while Blaine still depends on open terminals
and undocumented machine state. D1 makes the machine an understandable long-lived
host. Infrastructure PASS is narrower than service adoption, reboot recovery or
complete backup acceptance.

Start with [infrastructure ownership and paths](../platform-infrastructure.md),
[credential-free acceptance](../../infra/validation-d1-infrastructure.json),
[backup operations](../platform-operations.md), and [platform ADR 0018](../decisions/0018-local-platform-durability-and-observability.md).

### Implemented and proven foundation

Docker Engine / Compose run SeaweedFS S3-compatible Object Storage, ClickHouse,
Langfuse Web and Langfuse Worker. Native PostgreSQL and Redis are reused; native
Grafana Alloy collects local telemetry. systemd owns the top-level Compose stack
and Alloy; pragmatic Ansible records desired state. Stack, Docker and Alloy
restart/persistence smoke tests passed, including synthetic storage and Langfuse
roundtrips. A real infrastructure-only reboot passed on 2026-09-21 with a new boot ID and automatic recovery. It does not prove rootless boot recovery, full D1.G, or real cognitive traffic.

Persistent locations are explicit: `~/.local/share/blaine/infra/objects` includes SeaweedFS
metadata/filer/volumes; ClickHouse uses `~/.local/share/blaine/infra/clickhouse`. The
old `/srv/blaine/infra` tree is retained unchanged as the pre-cutover source; native
PostgreSQL uses `/var/lib/postgresql/18/main`; Redis uses `/var/lib/redis`; Alloy
uses `/var/lib/alloy`. The infrastructure runbook owns the detailed inventory,
versions, endpoints and config paths. Do not copy a historical inventory into a
new deployment without observing current state.

Object namespaces are `blaine-artifacts`, `langfuse-events` and `langfuse-media`,
with separate scoped access. The [Fleet control-plane slice](../platform-grafana-cloud.md)
reached **STOP for activation** on native Alloy 1.19.2 offline-start failure.
BWS/Keyring materialization and Fleet read-API access passed; local Alloy is restored
after that slice. The independent data-plane slice now exports metrics with Cloud
readback; restart-durable replay is unaccepted. No D1.G identity was replaced.
[ADR 0021](../decisions/0021-fleet-observability-control-plane.md) records the direction
without claiming adoption. Resolve and prove offline startup before enrollment;
do not introduce an alternate supervisor or reopen inference. Temporary maintenance
sudo was left untouched for human cleanup, not made a runtime dependency.

The durable knowledge/artifact brain is **PostgreSQL + Blaine Object Storage**.
Restate separately owns durable Task execution state and needs its own state path
preserved for Task recovery. This statement does not imply that PostgreSQL/S3 alone
reconstruct in-flight Tasks, or that the kernel's existing local ArtifactStore has
already been migrated to S3. D2 still uses its documented native state/artifact
paths; service adoption must account for the actual stores and their relationships.

### Backup — PAUSED

Design and isolated backup/restore test machinery exist. The identified Samsung
SSD backup filesystem was prepared with an authorized Blaine subtree, preserving
its historical backups. Physical/live PostgreSQL acceptance exposed a service
identity-switching failure before a successful generation/restore. Infrastructure
bring-up was intentionally prioritized. The timer remains disabled/inactive;
**backup is not complete** and the failed installed variant must be reconciled
before resuming. See [pause and volume evidence](../platform-d1.md).

Future complete durable-brain backup must cover PostgreSQL **and** Blaine Object
Storage, including the object store's metadata as well as object bytes. Existing
PostgreSQL plus selected file-artifact tests do not prove that coverage. Historical
backup data must remain untouched. Cloud/off-site backup is deferred.

### D1.A — Blaine service adoption

**Live adoption: PASS, 2026-09-21.** [Evidence and limitations](../platform-services.md).
Host reboot acceptance remains D1.G.

**Goal:** run actual Blaine application/runtime services under stable systemd
ownership rather than terminals. Select the accepted application entrypoint and
record release, config, secret references, state/artifact paths and dependencies;
do not promote an obsolete probe or migrate an active journal silently.

**Acceptance:** automatic start; observable health/readiness; controlled stop and
restart; the same durable Task remains inspectable and resumable after restart;
config is versioned where appropriate and secret values remain external. Coordinate
with D1.B so application registration and runtime ownership agree.

### D1.B — Restate service adoption

**Live adoption: PASS, 2026-09-21.** [Evidence and limitations](../platform-services.md).
Host reboot acceptance remains D1.G.

**Goal:** one stable long-lived Restate runtime with systemd ownership and an
explicit durable state directory. Inventory existing instances and registrations
before adoption; no accidental second runtime may mask a failed service.

**Acceptance:** automatic ownership/start, observable readiness, controlled restart,
correct Blaine deployment registration, and recovery of the same synthetic Task
identity/state. Record SDK/server/deployment versions and upgrade constraints.
D2 process-restart evidence is useful input, not host-service adoption evidence.

### D1.C — vLLM service adoption

**Live adoption: PASS, 2026-09-21.** [Evidence and limitations](../platform-services.md).
Host reboot acceptance remains D1.G.

**Goal:** replace the observed terminal-owned local inference process with
systemd ownership while capturing the actual version, model and serving config.
Do not change model behavior or introduce a benchmark program in this slice.

**Acceptance:** the configured model starts without a manual terminal; health is
observable; controlled restart succeeds; existing serving behavior is preserved
by a bounded authorized check. Account for any separate embedding service and GPU
resource dependencies actually used by the adopted configuration.

### D1.D — MIRIX service adoption

**Live adoption: PASS, 2026-09-21.** [Evidence and limitations](../platform-services.md).
Host reboot acceptance remains D1.G.

**Goal:** apply the same long-lived operational treatment to MIRIX. Observe its
actual process/dependency setup; preserve its PostgreSQL/object dependencies and
semantic-memory identity. Do not move Task state into MIRIX.

**Acceptance:** explicit service ownership, health/readiness and controlled restart;
a synthetic retained semantic memory can be retrieved after restart without loss.
Record dependency and inference readiness rather than assuming process start means
memory readiness.

### D1.E — Redis profiles (conditional)

**Goal:** investigate whether current consumers need separate ephemeral and durable
Redis profiles. Inventory cache/queue use, eviction and persistence requirements,
and failure behavior. The existing reuse is evidence, not a mandate to split.

**Acceptance:** a recorded decision backed by actual usage; implement separation
only if evidence justifies it, then validate consumer recovery and isolation.
A justified decision to retain the current instance also closes this investigation.

### D1.F — Backup continuation

Resume only after infrastructure/service priorities no longer dominate and the
backup pause is explicitly lifted for a bounded pass. Reconcile source versus
installed backup code and resolve the known service-identity defect before claiming
live success. Establish PostgreSQL + Blaine Object Storage coverage and a coherent
capture/restore boundary; separately document Restate recovery requirements.

**Acceptance:** write only within the dedicated namespace on the existing backup
filesystem; preserve historical data; fail closed for absent/wrong mount or UUID;
produce and verify a real generation; restore it in isolation and check database,
object identity/content and required metadata. Never substitute scratch machinery
PASS for physical/live acceptance. Do not enable the timer before accepted proof.

### D1.G — Full reboot acceptance

**Goal:** final D1 operational proof after required services are adopted:
healthy host → reboot → required services return → Blaine/Restate recover → local
inference, memory and storage return → synthetic durable state remains valid.

**Acceptance:** capture a reviewed pre-reboot service/dependency profile and recovery
plan; persist synthetic Task, semantic-memory and storage evidence; observe a new
boot identity and automatic service readiness; retrieve the same evidence and
resume the same Task. Report any recovery/backup limitations explicitly. Do not
manually start a duplicate supervisor to hide failed boot ownership.

**Requires explicit human authorization to reboot the machine.** Roadmap inclusion
is not reboot permission or permission to unpause backup. Refresh the old backup
runbook's historical reboot sketch against the adopted topology before executing
anything; Caddy/public exposure is not automatically a prerequisite for private v0.

## D2 — Personal Agent / Remote Task Intake

**STATUS: PASS.** [Boundary/run instructions](../daily-driver-d2.md),
[acceptance summary](../../experiments/daily-driver-d2/evidence/summary.json),
[validation/provenance](../../experiments/daily-driver-d2/evidence/validation.json).

**Why:** a durable kernel is not usable if every Task requires direct test/probe
interaction. D2 provides a human-facing control boundary without another runtime.

Proven: transport-neutral controls using the official ACP SDK; Task creation with
stable/idempotent identity (including concurrent requests); authoritative inspection;
result/artifact retrieval; typed HumanDecisionResponse; explicit native cancellation;
client/controller loss without implicit cancellation; controller restart without
Task loss; PolicyGate-protected capabilities; no second Task ledger or authoritative
chat history. The IntelliJ/ACP workspace **fixture** passed through real SDK calls.
The evidence covers five native Tasks, controller/runtime/Restate restarts and no
model calls. Identity guarantees have the documented retention boundary.

**Not proven:** live IntelliJ filesystem/project access, real investigation, real
edit, or real build/test execution. Those are D3. The earlier live IntelliJ/SSH
experiment proved session-independent Task control, not project filesystem access.
D2's private deterministic deployment and launch scripts are not completed D1
service adoption or a general natural-language coding agent.

<a id="d3"></a>
## D3 — Live IntelliJ / Real Code Tasks

**STATUS: PLANNED — delivered through the E1–E3 product gates after E0 connection.**

D3.A/B/C retain their historical meaning below. E1 delivers D3.A, E2 supplies
D3.B effects, and E3 is a synthetic full-loop proof that prepares D3.C rather than
automatically closing real-work readiness. See the [Hub acceptance/decomposition](../personal-agent-hub.md).

**Why:** this is the minimum practical threshold for Daily Driver use. Blaine must
work on repositories in the trusted company/work laptop environment, which already
owns the checkout, IDE/index, Git, JDK/build tools and required private network.
Use existing IntelliJ/ACP hooks. **Do not build a remote filesystem/workspace daemon
or export the workstation into Blaine.** Reachability and technical capability
never grant a Task all project authority.

### D3.A — Live read-only workspace proof

**Goal:** Personal Agent → durable Task → IntelliJ ACP → real project → authorized
scoped read/navigation → result → verifier. Start from D2's adapter and earlier
IntelliJ evidence rather than broad IDE research.

**Acceptance:** discover/open the actual project context; navigate/read a bounded
code location; restrict scope through PolicyGate and the client permission boundary;
return useful evidence through Personal Agent; survive controller/session loss with
the same Task. Use a safe project/area, avoid broad repository export, and record
which live hooks actually exist. Record or resolve D2's POSIX/WSL path and exact-digest
verification limitations in a bounded way rather than silently loosening them.

### D3.B — Small code change

Begin **only after D3.A passes**. Prefer a disposable or explicitly safe repository
and Task before sensitive work. Inspect the target, authorize narrowly scoped files
and tool effects, make a small edit, run the relevant test/build, capture the diff,
and retain artifacts/evidence. The deterministic CompletionVerifier must evaluate
the accepted contract; a worker exit or “done” message is insufficient. Acceptance
requires no unrelated changes and no expansion of workspace authority.

### D3.C — Real-work readiness

After controlled proofs pass, perform one genuinely useful, low-risk Task such as:
“Find this small duplication, refactor it, run relevant tests, show the diff.”
Retain the objective, grants, actual work, tests, diff, independent completion result
and any operator friction. This is the first deliberate real Daily Driver coding
acceptance, not permission to scale into arbitrary company repositories.

## D4 — Reusable Capability System

**STATUS: PLANNED.**

**Why:** YouTrack proved one vertical capability; IntelliJ/workspace supplies another;
Telegram will supply another. Without a reusable model, the Personal Agent risks
becoming a monolithic integration layer. Make capabilities discoverable, versioned
and reusable by later Tasks, guided by D3's actual integration friction.

Keep three questions separate: **capability** — what can technically be done;
**authority** — which concrete effects this Task may perform; **approval/autonomy** —
which authorized effects require a human decision. Neither discovery nor installation
may grant authority implicitly.

Candidate contract concerns, not a frozen registry schema: identity/version,
input/output contract, authority requirements, execution location, secret
dependencies, implementation binding and produced evidence. Early candidates are
YouTrack, IntelliJ/workspace actions, notification and future integrations.

A normal Task should eventually be able to produce a **Capability artifact**.
Installation/registration remains Blaine-owned and authority-controlled; Task-created
capability does not mean self-modifying kernel code. Prove one capability's bounded
creation/admission and reuse by a different Task before designing a universal catalog.

## D5 — Human Interaction Channels

**STATUS: PLANNED. Initial target: Telegram.**

**Why:** HumanDecision is already durable and typed, but currently requires the
control surface. Daily Driver needs asynchronous remote interaction. Build on D4's
capability seam where useful without making registry perfection a prerequisite.

**D5.A — Notifications:** Task completed → notify user. This is non-blocking and
must not suspend lifecycle. Provide a reusable notification capability, with delivery
failure visible independently of the Task's already verified completion.

**D5.B — Telegram HumanDecision transport:** existing HumanDecisionRequest → Telegram
adapter → question/options → user reply → typed HumanDecisionResponse → existing
Restate Task resumes. Preserve Task/request identity, revision, valid choices and
one-shot response admission across duplicate/stale delivery and adapter restart.
Telegram adds neither a new lifecycle nor a competing decision contract.

**D5.C — Capability provisioning:** support the eventual normal request “Blaine,
prepare Telegram notifications for me and make them reusable.” A Task may produce
or configure that capability under explicit authority; Blaine controls admission.
Use the project secret-management/materialization path. Secrets stay out of Git,
Task telemetry and conversation; endpoint configuration does not imply approval.

## D6 — Operational and Cognitive Observability

**STATUS: PARTIALLY IMPLEMENTED / ACCELERATED BY D1.**

**Why:** useful real Tasks need diagnosable failures and costs. This no longer means
installing the stack from zero: ExecutionEvent, ClickHouse, Langfuse, Alloy and a
Grafana Cloud activation path already exist. The remaining objective is to connect
real Blaine traffic appropriately and prove that the resulting information helps.

| Component | Role |
| --- | --- |
| ExecutionEvent | Semantic forensic evidence with Task/dispatch causality |
| Langfuse | Model/cognitive traces, generations, observed usage and latency |
| Alloy / Grafana | Host, service and application metrics, logs and traces |
| ClickHouse | Analytical/observability storage, including the deployed Langfuse dependency |

No observability component becomes authoritative runtime state. Preserve unknown
usage rather than inventing accounting, protect private content, and keep Task and
dispatch identifiers in appropriate event/trace fields instead of unbounded metric
labels. D2's local control/runtime event emission is a starting point, not full
backend integration.

Remaining examples: wire Personal Agent/runtime traffic, instrument actual cognition
and model calls, correlate logical identities with physical traces, build operational
dashboards/alerts, expose service and backup failures, and activate Grafana Cloud
when the account exists. Cloud activation should need only the already-documented
human credential/bootstrap steps in the [operator runbook](../platform-grafana-cloud.md),
not a new observability design. Verify delivery; configured is not connected.

## D7 — Blaine v0 Daily Driver Acceptance

**STATUS: PLANNED.** This is a product-readiness gate, not another architecture cycle.

| Scenario | Required end-to-end evidence |
| --- | --- |
| 1. Remote small Task | Remote submission creates durable work, completes under verification, and returns a result after client disconnect/reconnect. |
| 2. Real code investigation | Live IntelliJ/workstation capabilities inspect a real repository and return useful, evidence-backed output within scope. |
| 3. Small refactor | Read, narrowly modify, run relevant tests, return diff/artifacts, and independently verify completion without unrelated changes. |
| 4. Remote human decision | Task blocks, user receives Telegram question/options, response is admitted, and the same durable Task resumes and completes. |
| 5. Capability reuse | A capability installed/configured earlier is reused by another Task without rebuilding its integration. |
| 6. Runtime recovery | The authorized D1 recovery scenario occurs; services return and durable Task, memory and storage semantics remain intact. Distinguish process restart from host reboot and tested recovery from unproven backup coverage. |
| 7. Justified frontier use | When a real Task benefits, use a frontier worker under Increment 11 authority/context-projection constraints and verify the result. Frontier is optional per Task; record why it was used or not needed. |

Retain scenario evidence and explicit unresolved limitations. Do not equate component
PASS counts with the combined experience. Once these scenarios are sufficiently
proven against agreed scopes: **BLAINE v0 = DAILY DRIVER**. Frontier is not required
for every Task; advanced post-v0 cycles are not hidden prerequisites.

## Post-v0 Cycle A — Worker & Session Substrate

**Why:** the current worker boundary is sufficient for v0, but richer worker use
needs explicit session mechanics. Harvest useful Multica lessons without adopting
its runtime. Start from the [Multica carveout and limits](../research/multica-carveout.md)
and [replaceable harness ADR](../decisions/0016-agent-harnesses-are-replaceable-execution-capabilities.md).

| Slice | Intended contract / proof |
| --- | --- |
| A1 — Worker Session Contract | Bounded spawn, send, resume, collect and terminate primitives. Session state is execution plumbing, not Task state. |
| A2 — Continuity | `resume(session X)` resumes X or fails explicitly. Never silently create Y. Test missing/expired session and interruption behavior. |
| A3 — Result/Event Normalization | Provider-neutral streaming, output, artifacts, diagnostics, interruption, cancellation, usage and terminal status, with version-specific adapters and UNKNOWN where needed. |
| A4 — Worker Environment Assembly | Blaine constructs bounded ContextProjection, capabilities, skills, MCP/tools, filesystem scopes, environment and authority. The worker cannot broaden that environment or grant. |

Multica lessons to retain: adapters, independent sessions, spawn/resume/send/collect,
stream normalization, role/context separation, and environment/skill/tool assembly.
Rejected ownership: Task lifecycle, completion, hidden resume fallback, auto-approval,
scheduling, and duplicate queue/lease semantics already supplied by Restate. The
carveout observed invalid-resume fallback and incomplete interrupted usage; do not
promote those behaviors into Blaine's contract. Review upstream terms before any
future extraction/distribution, as recorded in that research.

## Post-v0 Cycle B — Context Compilation

**Why:** Increment 11 proved a security projection hook, not sophisticated context
preparation. As real Tasks grow, raw context becomes inefficient and may expose
unnecessary information. Produce the **smallest useful authorized context packet
that preserves enough information to succeed**. This is not permission to bypass
exact frontier projection or to make summarization authoritative.

| Slice | Plan and evidence gate |
| --- | --- |
| B1 — Context Compiler contract | Inputs: Task, authoritative source/artifacts, MIRIX, project knowledge, worker requirements and trust boundary. Output: bounded ContextPacket with provenance. Keep runtime facts and derived material distinguishable. |
| B2 — Deterministic selection | Start with relevant files/modules, relevant log windows, verified current Task facts and bounded memory retrieval. Retain source references/freshness and allow justified requests for more context. |
| B3 — Security projection / reversible pseudonymization | Implement deterministic transforms behind the Increment 11 hook: fictional organization aliases, domain aliases, sensitive values replaced by opaque stable tokens. Mapping dictionaries stay inside the trusted boundary; only Blaine-issued tokens can be reversed. Test rejection of invented/foreign tokens and raw-context bypass. |
| B4 — Structural condensation | Compiler output → relevant errors; test logs → failures/causal neighborhood; diff → changed semantic regions; project → relevant declarations. Prefer deterministic transforms first and preserve the route back to source evidence. |
| B5 — Context Fidelity Harness | Compare FULL, SELECTED and COMPILED on real Tasks. Measure verifier success, retries, context requests, tokens, latency and cost where observable. Keep grants and success criteria comparable; a FULL baseline still stays within its authorized boundary. Context fidelity is quality/evaluation, not PolicyGate authority. |
| B6 — Semantic condensation | Add only if prior evidence shows a need. Model summaries remain derived context and can never outrank authoritative source or weaken grants. |

The [frontier contract](../contracts/frontier-dispatch.md),
[protected-context ADR](../decisions/0013-protected-context-transformations.md) and
[context policy](../policies/local-first-and-context.md) constrain this work. Fidelity
failure should first challenge selection/condensation before blaming model ability.

## Post-v0 Cycle C — Routing, Failure and Escalation

**Why:** Increment 11 established static suitability/authority/accounting boundaries.
Smarter routing needs real execution history. Model failure caused by inadequate
context must not be misclassified as model capability failure.

**Current baseline: Policy C — local-first execution with bounded authorized
escalation**, accepted direction in [ADR 0024](../decisions/0024-local-first-execution-with-bounded-escalation.md)
and implemented in [milestone 042](../milestones/042-policy-c-local-first-escalation.md).
Every eligible Task starts locally, extra turns are a cost rather than a failure,
and escalation is a deterministic recommendation that only the trusted boundary
admits. It exists to produce the evidence a smarter pre-router would have to beat.

```text
Policy C — local-first + bounded authorized escalation     CURRENT BASELINE
  implementation ........................................  COMPLETE
  local execution .......................................  LIVE
  escalation detection ..................................  LIVE
  authority enforcement .................................  LIVE
  escalation evidence ...................................  LIVE
  remote escalation path ................................  IMPLEMENTED
  remote binding ........................................  NOT PROVISIONED

Policy B — deterministic heuristic pre-routing .........  FUTURE WORK
Policy A — classifier pre-routing (Jev) ................  INTEGRATED CANDIDATE,
                                                           NOT ADOPTED, FUTURE WORK
Controlled downgrade sampling ..........................  FUTURE WORK
C1 — failure classification ............................  FUTURE WORK
C4 — cost to successful completion ......................  FUTURE WORK
```

The distinction that matters most: **the escalation mechanism is implemented and
validated, and production remote escalation is not provisioned.** No deployment
configures an escalation binding, so the trusted boundary currently resolves every
recommendation to `denied_binding_unavailable`. That is the deployment state, not
a defect, and it is recorded in each routing record:

```text
local execution -> escalation condition -> trusted admission
                -> no provisioned remote binding -> denied_binding_unavailable
```

The first deployment to provision a remote binding can use that denial count as
one signal that the binding became reachable. No live Qwen-to-remote execution has
been demonstrated; the live acceptance showed local completion under an external
grant with no paid provider invocation.

The local turn budget and repetition threshold are **initial experimental
defaults**, not architectural invariants. Both are recorded in every routing
record so evidence gathered under one setting stays interpretable after it
changes. Revising them is a deliberate configuration change informed by observed
outcomes, not an ADR for each numeric adjustment.

| Slice | Plan and evidence gate |
| --- | --- |
| C1 — Failure taxonomy | Candidate distinctions: capability insufficient, context insufficient, policy denied, worker failure, tool failure, invalid output, external dependency and verifier rejection. Do not freeze categories before real cases support them. |
| C2 — Escalation semantics | **Partially implemented by Policy C**: a deterministic recommendation, trusted admission, escalation as an outcome rather than a diagnosis, and no self-issued grant. Still open: who judges previous capability insufficient, and what evidence warrants escalation beyond the two deterministic conditions in use. |
| C3 — Policy A, classifier pre-routing (Jev) | Jev is integrated, authenticated and **unadopted**; do not rebuild it and do not invent a use case for it. Adoption requires measured improvement against both Policy C and Policy B. Its existence is not a reason to place it in the runtime path. |
| C3b — Policy B, deterministic heuristic pre-routing | A cheap baseline any classifier must beat. The heuristic is deliberately undefined: derive it from real Policy C escalation evidence rather than inventing rules in advance. |
| C3c — Controlled exploration | Following a remote recommendation produces no evidence about whether local would have sufficed, so a router can become trivially conservative. A bounded downgrade sample must be randomized or explicitly defined, recorded, bounded, low-risk, distinguishable from normal routing, and unable to change policy automatically. |
| C4 — Cost-to-success routing | Optimize expected total cost to successful completion, not the cheapest invocation. Include retries, failure probability, escalation, runtime and observed cost where known; retain uncertainty for hidden accounting. |
| C5 — Learning-assisted routing | Begin offline: history → proposed policy → evaluation → human/promoted policy. No uncontrolled online self-modification initially. |

Use [frontier authority/suitability/accounting](../contracts/frontier-dispatch.md)
and [worker selection ADR](../decisions/0010-worker-selection-is-capability-and-quality-driven.md).
A suitability preference cannot override denied authority, and a cost ceiling does
not manufacture observability of provider internals.

## Post-v0 Cycle D — Project Knowledge

**Why:** graph/project knowledge may improve Context Compilation and code Tasks,
but must remain derived. Candidate work includes a provider contract, graph-assisted
selection, freshness/provenance and conflict semantics. Authority ordering is
**source/artifact truth > derived graph**. A stale graph is not permission to ignore
changed source or retain false certainty.

Harvest [Increment 9](../milestones/025-cognitive-kernel-increment-9-passed.md) and
[Graphify research](../research/graphify-carveout.md), including its freshness and
provenance counterexamples. Evidence may move this work into Context Compilation
earlier; neither a graph nor Graphify is required for v0 by default.

## Post-v0 Cycle E — Advanced Multi-Worker Patterns

**Why:** Increment 12 supplied durable child Tasks. Worker Sessions, context and
authority must mature before richer composition is useful and safe. The default
hot path remains **builder → artifact → deterministic verifier**.

Use an independent critic only when deterministic completion is insufficient for
the accepted quality question. Give it fresh, independently scoped context; it
produces evidence, not automatic completion. Parallel specialists use child Tasks,
WorkerSessions, role-scoped ContextPackets, explicit authority and typed outcomes.
Parent/child completion remains independent. Unconstrained multi-agent debate is
not the default, and parallelism should answer measured workload needs.

## How to resume development

A future human/agent should be able to resume from `main` without this conversation:

1. Read this roadmap, especially the current-next block and intentional unknowns.
2. Read the relevant [ADRs](../decisions/README.md), contracts and scoped policies.
   Form the smallest reviewable TaskSpec for durable work and use an available
   binding. If none fits, record the draft as unsubmitted; never invent runtime state.
3. Read the latest milestone/runbook and its evidence for the selected workstream.
   Check whether PASS is isolated, live, operational or product-level. Historical
   NEXT/STOP statements describe their checkpoint, not fresh authorization.
4. Inspect current `main`, `git status`, branch and worktree list. Inspect/fetch
   `origin/main` as needed to avoid overwriting remote work; observe the selected
   environment separately before relying on historical host facts.
5. Create a short-lived worktree/branch from current main for the bounded workstream.
   Assign one writer; define objective, exclusions, authority and observable acceptance.
6. Execute one bounded increment. Use direct observation and deterministic tools
   first. Do not start neighboring cycles or acquire broader authority implicitly.
7. Generate deterministic evidence, run focused checks and relevant regressions,
   and retain source/version/provenance and the limits of the result. Validate docs,
   local links and `git diff --check`; do not run live models/infra just for a docs pass.
8. Record **PASS or STOP** against acceptance. Update the selected milestone and this
   roadmap's status, evidence links, dependencies, unknowns and current-next block.
9. Inspect concurrent changes and stop on semantic conflicts; revalidate affected
   scope. Commit coherent bounded work. Integrate into main only within the current
   task's authorization; never overwrite concurrent work or infer merge permission.
10. Publish only when the current task explicitly authorizes it, then verify the
    authorized result. Historical checkpoint permissions are not standing authority.
    This Hub design slice requires one local commit and explicitly forbids push/merge.

**STOP is not failure.** It is expected when evidence reveals ownership ambiguity,
a lifecycle seam, an authority seam, source-of-truth ambiguity or a missing contract.
Record expected versus observed behavior, impact and the smallest decision needed.
A truthful safe STOP may integrate into main. Ordinary bounded implementation bugs
should normally be fixed rather than elevated into new architecture.

### Concurrent agents and worktrees

One agent/workstream owns one worktree. Other active worktrees are read-only;
read-only comparison does not authorize editing their working files. Synchronize
frequently with main, avoid long-running feature branches, preserve uncommitted
changes, and never overwrite concurrent work. Integrate accepted evidence, ADRs
and contracts quickly. Changes to lifecycle/authority/storage contracts deserve
semantic review even when Git merges cleanly. Main integration is the explicit
shared publication step, not permission to edit another feature worktree.

## Next-step decision guide

The default product sequence is **E0 → E1 → E2 → E3 → remaining D3.C / D4 / D5 /
D6 work as justified → D7**. D1 operations remain a separate track; an observed
service/safety blocker can interrupt the affected product slice. Paused backup,
Fleet, Cloud logs/traces, perfect Task-level OTel and telemetry restart durability
are not E0–E3 prerequisites. Operational reliability still gates final v0 acceptance.

| Evidence observed | Bounded priority adjustment |
| --- | --- |
| D3 fails because context is unusable | Consider pulling deterministic Context Compilation work forward; measure the failure before adding semantic condensation. |
| IntelliJ/ACP worker/session continuity blocks work | Pull the relevant Worker Session contract/continuity proof forward. |
| Rebuilding capability packaging is immediate friction | Prioritize D4 around the concrete duplicated integration. |
| Remote human interaction prevents useful unattended work | Prioritize D5 using existing HumanDecision contracts. |
| Real Tasks cannot be diagnosed | Prioritize D6 instrumentation and useful views on the deployed stack. |
| Service ownership or recovery loses availability/state | Prioritize the responsible D1 adoption/recovery slice before expanding workload. |

Record the evidence and resulting dependency change here; do not silently treat
these contingencies as authorization to implement an entire post-v0 cycle.

## Open questions / intentional unknowns

**Unknown means unresolved, not forgotten.** Keep each item until evidence or an
explicit decision closes it.

| Unknown | Evidence needed to resolve it |
| --- | --- |
| Hub client/platform/provider choices | [Explicit Hub open questions](../personal-agent-hub.md#open-questions), including WSL2/IDE live gates and safe write/exec |
| Final Capability Registry scope/shape | D3/D4 packaging, admission, versioning and cross-Task reuse experience |
| Redis profile separation | Actual cache/queue persistence, eviction and recovery requirements |
| When project graph belongs in the context path | Measured retrieval benefit with trustworthy freshness/provenance |
| Need for semantic condensation | FULL/SELECTED/COMPILED fidelity results showing a remaining deterministic gap |
| Whether Jev merits adoption | Measured improvement against Policy C and Policy B on cost to successful completion. Policy C now produces that evidence as a side effect of normal operation; a valid outcome is that no pre-router is worth its complexity |
| Precise escalation ownership/semantics | Real failure cases, attribution and a bounded recommendation/authority contract |
| Eventual custom UI | Concrete operator friction that ACP and remote channels cannot reasonably address |
| Complete backup/off-site strategy | PostgreSQL/Object Storage coverage, Restate recovery needs, isolated restores, agreed recovery objectives and later off-site requirements |
| Provider-native accounting availability | Version/binding observations distinguishing known usage from hidden calls, retries and cost |

### Maintaining this handoff

Change status only with a linked milestone/decision and the evidence supporting its
scope. Record deferrals and failed attempts without retroactive success. Update the
current-next block in the same accepted increment, and replace stale active entrypoint
claims with links rather than duplicating this roadmap. ADRs own architectural
rationale, contracts own interfaces, milestones own measured outcomes, runbooks own
operator procedures; this document owns development direction and dependencies.

<a id="current-next"></a>
## Current next work

- **Track A: Personal Agent Hub E0–E3.** **E0.A foundation PASS**: standalone
  client, platform/config locations and clean stdio/process proof
  ([evidence](../../experiments/e0a-blaine-client/README.md)). **E0.B native Linux
  network prerequisite PASS / cross-platform PARTIAL**
  ([evidence](../../experiments/e0b-tailscale-onboarding/README.md)). **E0.C PASS**
  ([closure](../../experiments/personal-agent-hub/e0c-direct/closure.json)): embedded
  tsnet/direct transport, primary Mac real IntelliJ read-only round trip, persistent
  identity/reconnect, narrow effective policy, canonical persistent Hub and bounded
  Task independence. Public alpha.3 is the current proven client; alpha.1 is historical
  SSH product-transport evidence. WSL transport proof retains its metadata limitation;
  full Windows-hosted IntelliJ/WSL acceptance belongs to E0.F. **E0.D Registration**
  is the next canonical slice, unblocked and not started. E0.D+ was not implemented.
  Use the [design and decomposition](../personal-agent-hub.md#implementation-decomposition).
  Full E0 onboarding then E1 read, E2 effects and E3 coding each require their own gates.
  D3 history is preserved; no full E-series milestone is claimed live PASS.
- **Track B: D1.A/B/C/D live adoption accepted.** Run the prepared D1.G reboot
  acceptance only with explicit human authorization; backup stays PAUSED.
- **Backup: PAUSED.** Preserve historical backup data; no live backup completion claimed.
- **Grafana Cloud metrics: ACCEPTED best-effort; current slice CONCLUDED.**
  Live delivery, network retry/drain and offline local startup passed. Restart
  replay remains unguaranteed, not a D1.G blocker. [OBS-001 / NCP-3](https://leofuso.youtrack.cloud/issue/NCP-3)
  tracks future durability investigation in Upstream/Backlog. Fleet remains
  DEFERRED / STOP; logs/traces export is inactive. See the
  [live inventory and validated PromQL](../platform-observability-inventory.md).
- **Blaine observability coverage:** current coverage/gaps and its independent
  operational follow-ups live in the [observability inventory](../platform-observability-inventory.md)
  and [GPU/vLLM runbook](../platform-gpu-vllm-telemetry.md). Additional coverage is
  outside the E0–E3 critical path unless a concrete product blocker requires it.
  This is separate from OBS-001 and does not change D1.G's Cloud independence.
- **D2: PASS.** Live IntelliJ project access and real code execution remain D3 work.
- **Cognitive Kernel 1–12: COMPLETE.** No further kernel increment is scheduled.
- **Secret delivery: ADR 0023 accepted.** Bitwarden is the source of truth and not
  a runtime dependency; SecretSpec 0.20.0 resolves declared secrets behind one
  alias while Blaine keeps the consumer allowlist, atomic activation, verification
  and rotation reporting. Services and bounded processes start from local `0600`
  credentials with the secret manager, the keyring and a desktop session all
  unavailable. Credentials remain plaintext at rest, recorded as an accepted
  limitation. See the [secrets runbook](../platform-secrets.md).
- **Jev: integration PASS, NOT adopted.** One real authenticated invocation exists
  and Jev changes no routing outcome. C3's comparison is still unstarted; see
  [milestone 041](../milestones/041-jev-provider-candidate.md).
- **Policy C — local-first execution with bounded escalation: COMPLETE.**
  [ADR 0024](../decisions/0024-local-first-execution-with-bounded-escalation.md)
  is accepted for its mechanism. Every eligible Task starts on the local binding,
  escalation is deterministic and trusted, and each Task retains authoritative
  routing evidence that a deterministic report reads. Effective capability
  authority is now the request intersected with an external grant, closing a real
  gap where a top-level Task declared its own authority. **No production remote
  binding is provisioned**, so escalation currently denies as unavailable by
  design. Policies A and B remain future work; nothing routes by classifier or
  heuristic. See [milestone 042](../milestones/042-policy-c-local-first-escalation.md).
- **Worker execution boundary: user-directed increment, PASS within its evidence.**
  A provider-neutral continuation boundary, adapter capability claims and an
  OpenTelemetry telemetry path now exist, with a synchronous control hook where an
  adapter genuinely provides one. Codex app-server exposes observation, steering and
  interruption but **not** synchronous continuation admission, which is declared
  UNSUPPORTED rather than emulated. This changes no workstream status, adopts no
  worker binding and builds no supervisor or dashboard. See
  [milestone 040](../milestones/040-worker-execution-instrumentation.md) and the
  [boundary contract](../contracts/worker-execution-boundary.md). Selective semantic
  supervision, steering policy and rebinding policy remain unstarted.

This checkpoint includes E0.A/B and partial E0.C; it does not claim full E0–E3/D3 acceptance,
adopt services, change Platform D1 infrastructure, unpause backup or authorize a reboot.

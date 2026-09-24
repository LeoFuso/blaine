# Blaine — Personal Agentic Development Kit

> Historical planning material. Current sequencing, accepted status and next work
> live in the [development roadmap](roadmap/001-blaine-development-roadmap.md).
> Build sequences, estimates and next steps below are retained context, not current commitments.

> **North Star / Working Architecture**
>
> Blaine is a personal agentic work system: a durable, context-aware control plane that turns intent into tasks, chooses the right tools and agents, keeps execution state outside the LLM, minimizes paid cloud inference, and lets the user steer work interactively from the IDE.

> Examples in this document are intentionally generic so the public repository does not encode employer-, client-, or project-specific operational details.

Current [ADRs](decisions/README.md) take precedence over this document's older
exploratory topology, routing, contract, and build-sequence examples. Proposed
ADRs remain proposals; examples do not establish acceptance or implementation.

For current ownership, read [architecture](architecture.md). For workstation/client
product design, read [Personal Agent Hub](personal-agent-hub.md). The exploration
below remains historical; it is not a parallel current architecture document.

---

## 1. What Blaine Is

Blaine is **not** a coding agent, an IDE, or a generic open-source agent framework.

It is the user's **personal agentic work system**.

The primary interaction is conversational:

- "Investigate this CI pipeline failure."
- "Review this branch and tell me what matters."
- "Check Slack and summarize what needs my attention."
- "Implement this ticket, test it, and show me the diff."
- "Watch this thread and tell me if someone answers."
- "Run this overnight and give me the result tomorrow."

Coding is one of the most important workloads, but it is only one workload.

The system should help the user work **agentically** across development, communication, investigation, research, monitoring, and personal workflows.

---

## 2. Product Shape

Think of Blaine as three related layers.

### Blaine Agent

The conversational interface and personal coordinator.

Responsibilities:

- understand user intent;
- create or modify tasks;
- explain current task state;
- ask for decisions when required;
- surface evidence and results;
- steer active workflows;
- interact with the ADK and runtime.

The Blaine Agent does **not own task execution state**.

### Blaine ADK

The toolkit and contracts used to define agentic work.

It defines concepts such as:

- Task;
- Context Policy;
- Cloud Budget;
- Capabilities;
- Autonomy Policy;
- Completion Contract;
- Scheduling;
- Agent Adapter;
- Verifier;
- Harness Profile.

### Blaine Runtime

The durable execution layer.

Current implementation of the Durable Runtime role: **Restate**.

Responsibilities:

- persist task/workflow state;
- retries and backoff;
- timers and schedules;
- signals and user input;
- pause/resume/cancel;
- child workflows;
- crash recovery;
- long-running execution;
- deterministic lifecycle management.

---

## 3. Core Architecture

**Historical exploratory topology:** the diagram below is retained for context,
not as current ownership or routing guidance. Its separate "Decision Plane" is
now covered by Personal Agent / Semantic Triage responsibility; ACP belongs to
client integration, not the execution-worker categories shown here.

```text
                        USER
                         │
              IntelliJ / CLI / future UI
                         │
                         ▼
                  ┌──────────────┐
                  │ BLAINE AGENT │
                  └──────┬───────┘
                         │
                    Blaine ADK
                         │
                         ▼
              ┌─────────────────────┐
              │   BLAINE RUNTIME    │
              │      Restate        │
              │ durable execution   │
              └─────────┬───────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
          ▼             ▼             ▼
   Context Engine    Decision      Work Engine
                     Plane
          │             │             │
          │        local models        │
          │       Qwen/Nemotron        │
          │             │             │
          └──────┬──────┴──────┬──────┘
                 │             │
                 ▼             ▼
           Agent Adapters    Verifiers
          ┌──────┼──────┐      │
          │      │      │      ├── Maven/tests
        Codex  Goose   ACP     ├── Git state
                               ├── CI
                               └── domain checks
```

External systems remain sources of truth:

```text
Git / GitLab / Jira / Slack / IntelliJ / filesystem / documents / APIs
```

---

## 4. The Four Kinds of Memory

These must remain distinct.

### 4.1 Working Memory — LLM Context

Temporary context needed for the current reasoning step.

It is expensive, lossy, and disposable.

Never treat chat history as authoritative workflow state.

### 4.2 Execution Memory — Durable Runtime (currently Restate)

Authoritative operational state:

- task status;
- workflow position;
- attempts;
- retries;
- timers;
- waiting signals;
- child executions;
- intermediate execution results.

Restate replaces the role previously imagined for a SQLite-based task ledger **for execution state**.

### 4.3 Knowledge Memory — Context Catalog

Reusable knowledge about the user's world:

- projects;
- systems;
- repositories;
- architecture;
- ownership;
- generated summaries;
- dependencies;
- known workflows;
- past task artifacts;
- useful context mappings.

This does **not** need to be sophisticated in V1.

It may initially be files + Git metadata + small structured indexes.

### 4.4 Sources of Truth — External Systems

Examples:

- repository state;
- GitLab MR state;
- Jira ticket state;
- Slack messages;
- IntelliJ symbols/indexes;
- CI results;
- documents.

Generated summaries never outrank authoritative source state.

---

## 5. Token Economics

The goal is **not** to minimize local-model tokens.

Local inference on Blaine's GPU is effectively abundant until it harms latency or quality.

The scarce resource is **paid cloud inference**.

Therefore the optimization boundary is:

```text
LOCAL WORLD                              CLOUD

metadata                                Codex / cloud model
search                                  ────────────────►
Git                             minimal context packet
IntelliJ indexes
cached summaries
Qwen / Nemotron
local reasoning
context ranking
```

It is acceptable to spend large local context windows to determine the smallest useful cloud packet.

### Cloud calls should answer three questions

1. Does this task actually require cloud intelligence?
2. What is the smallest context packet that preserves quality?
3. Can the result be verified locally?

Every cloud invocation should eventually be attributable to:

- task;
- reason;
- model/agent;
- supplied context;
- cost/tokens;
- outcome;
- verification result.

---

## 6. Context Engineering

The Context Engine is a first-class subsystem.

Its job is not to load everything. Its job is to answer:

> **What does this worker need to know right now?**

Inspired by Spotify's platform/context approach, but intentionally personal and lightweight.

Example conceptual catalog:

```text
Example Workspace
│
├── Projects
│   ├── service-a
│   ├── gateway-service
│   └── shared-infrastructure
│
├── Systems
│   ├── Payments
│   ├── Notifications
│   ├── Identity
│   └── CI/CD
│
├── Sources
│   ├── IntelliJ
│   ├── GitLab
│   ├── Jira
│   ├── Slack
│   └── repo docs
│
└── Knowledge
    ├── architecture summaries
    ├── dependency relationships
    ├── generated context artifacts
    └── prior task evidence
```

Context is resolved **just in time**.

Do not create a universal giant prompt.

---

## 7. Bounded Semantic Decisions

The Personal Agent owns semantic interpretation/triage; this is not a separate
Decision Plane. Worker Selection owns capability/quality eligibility.

Local models are valuable, but they should make **bounded semantic decisions**, not pretend to be the runtime.

Good uses for Qwen/Nemotron:

```text
classify(task)
rankContext(task, candidates)
needsCloud(task, evidence)
chooseWorker(task, capabilities)
summarizeForCloud(context)
classifyFailure(result)
needsUserDecision(task)
```

Bad use:

```text
"You are the CTO. Manage subprocesses, retries, workspaces, Codex CLI,
state, schedules and completion entirely through a prompt."
```

Whenever policy code can make a decision reliably, prefer policy code.

Historical early routing sketch (not current policy; task type does not select a
concrete model or worker):

```text
simple deterministic lookup     → tools first
local summarization             → local model
mechanical edit                 → local/cheap worker
substantial repository change   → Codex
code review                     → independent reviewer
waiting for an event            → Restate, no LLM
```

The router should become learned/smarter only after telemetry exists.

---

## 8. Work Orchestration

Learn from Symphony and Cursor.

### Task > Session

The task is the durable unit of work.

A chat session, model turn, Goose session, Codex process, or IDE window is temporary.

### Agent exit != Task completion

A worker returning exit code 0 means only:

> that worker invocation ended successfully.

It does not mean the requested outcome exists.

Completion belongs to the task runtime and verifier.

### Runtime manages lifecycle; agents do work

The Durable Runtime (currently Restate) manages lifecycle; illustrative states:

```text
RUNNING
WAITING
RETRYING
BLOCKED
VERIFYING
COMPLETED
CANCELLED
```

Do **not** encode every reasoning step as a workflow state.

The runtime controls lifecycle, not thought.

### Workers are replaceable adapters

```text
AgentAdapter
├── CodexAdapter
├── GooseAdapter
└── future adapters
```

Codex is a powerful worker, not part of the architecture itself. ACP is a client
integration protocol, not an execution-worker category.

---

## 9. Harness Engineering

Blaine's harness is the environment that makes agents effective.

It includes:

- context available to the worker;
- repository/project knowledge;
- tools;
- MCP servers;
- skills;
- policies;
- validation commands;
- feedback loops;
- task instructions;
- workspace boundaries;
- permissions;
- completion evidence.

`BLAINE.md` is **not** the harness.

It should become a small map / entry point using progressive disclosure.

Do not make every worker ingest the entire operating manual.

---

## 10. Task Contract

Historical exploratory contract example; use the current [TaskSpec contract](contracts/task-spec.md)
for field meanings and cloud authorization. This example is not a valid TaskSpec:

```yaml
objective: investigate service routing regression

mode: interactive

context:
  domain: example-platform
  projects:
    - service-a
    - gateway-service

budget:
  local_inference: unrestricted
  cloud: prefer-zero
  max_cloud_usd: 5

capabilities:
  - intellij
  - git
  - gitlab
  - codex
  - shell

completion:
  - explain root cause
  - provide evidence

autonomy:
  destructive_actions: ask
  git_push: ask

schedule: null
```

This is illustrative, not a committed schema.

The important abstraction is:

```text
Task
├── objective
├── context policy
├── execution policy
├── cloud budget
├── capabilities
├── completion contract
├── autonomy
└── scheduling
```

---

## 11. Primary User Experience

The desired interaction is **interactive first**, with durable execution underneath.

Example:

```text
User: Blaine, what needs my attention?

Blaine:
- A code review task is waiting for your review.
- A CI pipeline failed again in the test environment.
- Two Slack replies look relevant to an API migration.

User: Investigate the pipeline failure first. Do not change anything.
```

Blaine creates a durable task:

```text
Task #417
mode: interactive
autonomy: read-only
status: RUNNING
```

The user can continue talking while it runs.

Later:

```text
User: Where is the pipeline investigation?

Blaine:
Task #417
RUNNING
currently: inspecting pipeline logs
elapsed: 3m12s
```

The user can steer it:

```text
"Cancel it."
"Continue, but don't touch the shared environment."
"Ask Codex to review the proposed fix."
"When tests pass, show me the diff before pushing."
```

Closing IntelliJ must not destroy the task.

---

## 12. IntelliJ as the First Client

Do not build a custom UI first.

Preferred first client:

```text
IntelliJ AI Chat
      │
      │ ACP
      ▼
Blaine ACP bridge / agent
      │
      │ Tailscale / local network
      ▼
Blaine Runtime on server
```

This gives the user a conversational Blaine directly inside the primary development environment.

Potential later clients:

- CLI;
- small web UI;
- mobile/notifications;
- Slack;
- ChatGPT or another conversational client.

Air may later be useful as a specialized development frontend, especially for worktree/task visualization and code review, but it is not required for the initial architecture.

---

## 13. Initial Vertical Slices

Only two initial workloads.

### A. Development task

Example:

> "Blaine, fix this failing test."

Exercises:

- IntelliJ interaction;
- task creation;
- project context;
- workspaces;
- Codex adapter;
- verification;
- interactive steering;
- completion evidence.

### B. Information task

Example:

> "Read these messages and tell me what matters."

Initially this can use a local fixture; Slack integration comes later.

Exercises:

- external/information source;
- local inference;
- filtering;
- summarization;
- durable scheduling;
- user delivery.

If the same Task + Runtime + Agent architecture can support both, the architecture is likely pointed in the right direction.

---

## 14. Non-Goals

Do **not** build these unless a real personal need appears:

- custom IDE;
- editor;
- diff viewer;
- terminal emulator;
- generic issue tracker;
- generic SaaS multi-tenant platform;
- new durable-execution engine;
- new model harness;
- custom Git implementation;
- broad Kubernetes support;
- generic marketplace/plugin ecosystem;
- polished frontend before the runtime proves useful.

If the project starts becoming "our own Air/Cursor", stop and reassess.

---

## 15. Ten Rules to Keep Us Focused

1. **Task is the unit of work. Chat/session is not.**
2. **The Durable Runtime (currently Restate) owns execution state. LLMs do not.**
3. **LLMs make semantic decisions; code manages lifecycle.**
4. **Local inference is abundant. Paid cloud inference is scarce.**
5. **Context is resolved just-in-time, not universally loaded.**
6. **Cloud receives the smallest context packet that preserves quality.**
7. **Agents are replaceable adapters. Codex is not the architecture.**
8. **Completion requires outcome/evidence, not an agent saying "done".**
9. **Interactive-first; overnight/background execution is a capability, not the product.**
10. **Do not build UI until IntelliJ + Restate UI + CLI reveal a real missing UX.**

---

## 16. First Milestone — The Skeleton Breathes

The first milestone is intentionally boring.

```text
IntelliJ
   ↓ ACP
Blaine Agent
   ↓
create Task
   ↓
Restate workflow
   ↓
run one deterministic activity
   ↓
return status/result
   ↓
IntelliJ
```

No Codex.
No Slack.
No sophisticated Context Engine.
No multi-agent planner.
No custom dashboard.

### Definition of Done

- user can talk to Blaine from IntelliJ;
- Blaine can create a durable task;
- the task survives client disconnect/restart;
- Blaine can query task status;
- task can execute at least one activity;
- user can cancel or signal the task;
- result returns to the conversation;
- execution is visible in Restate observability.

Once this works, add capabilities incrementally.

---

## 17. Proposed Build Sequence

### Phase 0 — Preserve the decisions

- commit this document;
- keep architecture decisions small and explicit;
- stop current Qwen/Nemotron orchestration benchmarks;
- retain existing failure traces as regression evidence.

### Phase 1 — Runtime skeleton

- self-host Restate on Blaine;
- create minimal task service/workflow;
- activity execution;
- status query;
- signal/cancel;
- inspect execution in Restate UI.

### Phase 2 — Personal Agent / IntelliJ

- create minimal ACP-compatible Blaine agent/bridge;
- connect IntelliJ AI Chat;
- expose task create/status/cancel operations;
- conversationally drive a Restate task.

### Phase 3 — Development vertical slice

- workspace abstraction;
- Git worktree support if needed;
- Codex adapter;
- verifier adapter;
- simple completion contract;
- interactive steering.

### Phase 4 — Information vertical slice

- local information fixture;
- local-model filtering and summarization;
- scheduled task;
- eventually Slack connector/API.

### Phase 5 — Context Engine V1

- project/context catalog;
- JIT context resolution;
- IntelliJ/Git context providers;
- cached context artifacts;
- provenance.

### Phase 6 — Cloud economy / routing

- cloud invocation telemetry;
- context packet measurement;
- basic policy router;
- local-first decision helpers;
- paid-token/cost accounting.

### Phase 7 — Hardening

- retries;
- crash recovery tests;
- stale context detection;
- verifier failures;
- approval boundaries;
- regression suite derived from real failures.

---

## 18. Expected Time

This is not a one-evening project, but it does not need to become a multi-month platform effort either.

A realistic expectation for focused experimentation:

```text
1–2 days     prove Restate + task contract + basic runtime
1–2 days     IntelliJ ACP → Blaine → Restate vertical connection
1–3 days     first useful development workflow
1–2 days     first useful information workflow
several days context/routing/telemetry improvements
```

So:

- **a few focused days** to prove the architecture end-to-end;
- **roughly 1–2 weeks of iterative work** to reach something genuinely useful in daily work;
- continued evolution driven by actual use rather than a large up-front platform build.

Do not optimize for completeness. Optimize for the first daily workflow that feels meaningfully better than manually juggling chats, terminals, CLIs, and browser tabs.

---

## 19. Architecture References / Mental Models

Blaine should borrow ideas, not blindly copy products.

### Spotify

Use a context/catalog mindset:

- systems and projects are discoverable;
- relationships are explicit;
- relevant context is addressable;
- agent context is platform context.

### OpenAI Harness Engineering

The repo/environment/harness should make agents effective through:

- small entry-point instructions;
- progressive disclosure;
- tools;
- validations;
- feedback loops;
- environment design.

### OpenAI Symphony

Borrow:

- Task > Session;
- Workspace per task;
- Agent Runner abstraction;
- reconciliation;
- retries;
- worker success != task completion.

### Cursor

Borrow:

- durable agent execution;
- workflow state independent of process lifetime;
- long-running tasks should survive failures;
- agent loop, machine state, and conversation state are separate concerns.

### Restate

Current implementation of the Durable Runtime role:

- workflows;
- durable state;
- timers;
- retries;
- signals;
- long-running execution;
- pause/resume/cancel;
- operational visibility.

### JetBrains / ACP

Use the IDE as a client rather than building an IDE:

- Blaine is exposed as an agent;
- IntelliJ provides the conversational surface;
- IDE/MCP context can become one context provider among many.

---

## 20. Decision Log — Current Commitments

Current working decisions:

- Blaine is personal-first, not a generic product.
- Coding is a major workload, not the whole system.
- Interactive work is the default experience.
- Background/overnight execution must be possible but is secondary.
- Restate is the current implementation of the Durable Runtime role.
- IntelliJ via ACP is the current preferred first user interface.
- Paid cloud inference should be minimized; local inference need not be.
- Local models are decision/context workers, not the workflow engine.
- Codex is a replaceable high-capability worker.
- Context engineering is a first-class concern.
- No custom frontend until a concrete UX gap appears.

These are working architectural decisions, not immutable truths. Change them only when evidence from real use justifies it.

---

## 21. Immediate Next Step

Do **not** run another orchestration benchmark yet.

Build the smallest possible end-to-end spike:

```text
IntelliJ → ACP Blaine → create Restate Task → deterministic activity → task status → response in IntelliJ
```

Once that works, the architecture exists outside of diagrams.

Everything else can grow from there.

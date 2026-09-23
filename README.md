# Blaine

Blaine is a personal-first agentic work system: a human-facing coordinator for
real work backed by durable Tasks. Coding, investigation, research and personal
operations share the same boundary: **Task > session**.

**Start with the [living development roadmap and repository handoff](docs/roadmap/001-blaine-development-roadmap.md).**
It records what is proven, what remains incomplete, why the next workstreams
exist, and how to resume without prior conversation history.

Current development is Daily Driver Enablement. The next bounded product sequence
is [Personal Agent Hub E0–E3](docs/personal-agent-hub.md): connect a workstation,
read its workspace, add bounded effects, and prove verified coding with a human
response. This is an accepted design, not implemented product acceptance. See the
[roadmap](docs/roadmap/001-blaine-development-roadmap.md#current-next) for current
implementation status, evidence limits and dependencies.

Restate owns Task lifecycle and recovery. Models propose bounded semantic work;
PolicyGate authorizes effects and deterministic CompletionVerifier owns completion.
Clients, workers and conversations are replaceable. Local inference comes before
unnecessary paid frontier inference; cloud dispatch remains authority-controlled.

## Repository navigation

| Start here | Purpose |
| --- | --- |
| [Development roadmap](docs/roadmap/001-blaine-development-roadmap.md) | Current program, priorities, dependencies and handoff |
| [Track III: context, memory and verified learning](experiments/track-iii-002/README.md) | III.2 deterministic semantics PASS; III.3 proposed and unstarted; no runtime adoption |
| [Documentation map](docs/README.md) | Canonical sources: architecture, status, contracts, operations and historical evidence |
| [Personal Agent Hub E0–E3](docs/personal-agent-hub.md) | Canonical workstation/client product design and implementation gates |
| [Architecture](docs/architecture.md) and [ADR index](docs/decisions/README.md) | Ownership and architectural decisions; respect each ADR's status |
| [Milestones and progress](docs/milestones/README.md) | Accepted evidence and historical STOPs |
| [TaskSpec](docs/contracts/task-spec.md) and [Task operations](docs/contracts/task-operations.md) | Request and control contracts |
| [Frontier dispatch](docs/contracts/frontier-dispatch.md) and [ExecutionEvent](docs/contracts/execution-event.md) | Authority/context boundary and forensic evidence |
| [Platform foundation](docs/platform-infrastructure.md) and [rootless operations](docs/platform-rootless-docker.md) | Infrastructure topology and operator ownership |
| [Adopted runtime services](docs/platform-services.md) | Application services, readiness, state paths and recovery procedure |
| [Live observability inventory](docs/platform-observability-inventory.md) | Actual host/GPU/vLLM/log/trace coverage and Cloud-validated PromQL |
| [Metrics data plane](experiments/d1-grafana-cloud-data-plane/README.md) | Historical acceptance and transport durability limits |
| [Fleet control plane](docs/platform-grafana-cloud.md) | Fleet setup, activation gates and recovery |
| [Operations/recovery](docs/platform-operations.md) and [Grafana Cloud activation](docs/platform-grafana-cloud.md) | Operator procedures, paused backup and future activation |
| [Personal Agent / D2](docs/daily-driver-d2.md) | Private ACP control surface, usage, acceptance and live-workspace limits |
| [Agent instructions](BLAINE.md) and [skills](skills/SKILL.md) | Conversational triage and Task operation procedures |

## Working on Blaine

Use a short-lived worktree from current `main`, select one bounded roadmap
increment, and preserve other worktrees. Read the relevant contracts and latest
milestone before editing. Retain deterministic PASS or truthful STOP evidence,
then integrate a coherent state promptly. See the roadmap's resume procedure.

`runtime/` contains implementation, `tests/` deterministic checks, `experiments/`
retained acceptance evidence, and `infra/` platform desired state and validation.
Follow the D2 and platform runbooks for their respective setup paths; a clone
alone does not deploy the host or provision private credentials. Secrets stay
outside Git. This repository does not yet claim complete Daily Driver v0 readiness.

## License

[MIT](LICENSE). Created by Leo Fuso (@leofuso).

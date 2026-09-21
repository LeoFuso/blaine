# Blaine

Blaine is a personal-first agentic work system: a human-facing coordinator for
real work backed by durable Tasks. Coding, investigation, research and personal
operations share the same boundary: **Task > session**.

**Start with the [living development roadmap and repository handoff](docs/roadmap/001-blaine-development-roadmap.md).**
It records what is proven, what remains incomplete, why the next workstreams
exist, and how to resume without prior conversation history.

The Cognitive Kernel program (Increments 1–12) is complete. Current development
is Daily Driver Enablement: D1's infrastructure foundation and rootless migration
passed, with remaining service adoption and reboot acceptance pending; D2's Personal Agent control surface passed its
bounded acceptance. Live IntelliJ/code work is D3, not yet proven.

Restate owns Task lifecycle and recovery. Models propose bounded semantic work;
PolicyGate authorizes effects and deterministic CompletionVerifier owns completion.
Clients, workers and conversations are replaceable. Local inference comes before
unnecessary paid frontier inference; cloud dispatch remains authority-controlled.

## Repository navigation

| Start here | Purpose |
| --- | --- |
| [Development roadmap](docs/roadmap/001-blaine-development-roadmap.md) | Current program, priorities, dependencies and handoff |
| [Documentation index](docs/README.md) | Map of maintained documentation |
| [Architecture](docs/architecture.md) and [ADR index](docs/decisions/README.md) | Ownership and architectural decisions; respect each ADR's status |
| [Milestones and progress](docs/milestones/README.md) | Accepted evidence and historical STOPs |
| [TaskSpec](docs/contracts/task-spec.md) and [Task operations](docs/contracts/task-operations.md) | Request and control contracts |
| [Frontier dispatch](docs/contracts/frontier-dispatch.md) and [ExecutionEvent](docs/contracts/execution-event.md) | Authority/context boundary and forensic evidence |
| [Platform foundation](docs/platform-infrastructure.md) and [rootless operations](docs/platform-rootless-docker.md) | D1 installed stack, rootless migration PASS and pending reboot acceptance |
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

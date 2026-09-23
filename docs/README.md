# Blaine documentation

Use this map to locate the authority for a question. Current architecture, current
implementation status and historical proof are different concerns; a later date
or a PASS label alone does not make a document authoritative outside its scope.

## Where should I look?

| Question | Canonical source | Role / limit |
| --- | --- | --- |
| What is Blaine? | [Repository README](../README.md) | Concise entry point and orientation; links to detailed authority. |
| How is the current system organized? | [Architecture](architecture.md) | Current ownership and system boundaries; no implementation chronology. |
| What is implemented, what comes next, and what blocks it? | [Development roadmap](roadmap/001-blaine-development-roadmap.md) | Current program status, dependencies, scope of acceptance and next work. Follow evidence links; this is not a live host-health read. |
| How should workstation/client integration work? | [Personal Agent Hub E0–E3](personal-agent-hub.md) | Canonical product-boundary design, accepted/recommended/open decisions, platform targets and implementation gates. Planned functionality is labeled. |
| How do I build/use the workstation client foundation? | [E0.A client guide](../client/README.md), [evidence](../experiments/e0a-blaine-client/README.md) | Implemented command subset and standalone build proof; full onboarding and macOS/WSL2 runtime remain unvalidated. |
| Which secret backends and provider candidates exist, and what is actually adopted? | [Secret delivery](platform-secrets.md), [Jev candidate](../experiments/jev-provider-carveout/README.md) | Adopted secret lifecycle versus an unadopted routing candidate. A provider integration existing is not adoption; C3 still gates that. |
| How is Worker execution observed and controlled at a model continuation boundary? | [Worker execution boundary](contracts/worker-execution-boundary.md), [evidence](../experiments/worker-execution-instrumentation/README.md) | Boundary definition, adapter capability claims, control/telemetry split and durability rules. Capability claims are version-scoped observations, not permanent harness guarantees. |
| Which interfaces and invariants are normative? | [Contract index](contracts/README.md), [policies](policies/task-completion-and-lifecycle.md) | Versioned intent/control/evidence/authority contracts and enforcement rules. Wider design contracts are not proof of implemented binding support. |
| Why was an architectural choice made? | [ADR index](decisions/README.md) | Accepted/proposed/superseded decision history and rationale. Validation sections link proof; ADRs are not operational status pages. |
| How is the host deployed and operated? | Platform map below | Current topology, paths, deployment and runbooks; distinguish dated observations from live state. |
| What does the existing Personal Agent binding support? | [D2 binding guide](daily-driver-d2.md) | Implemented control subset, usage and acceptance limits; E-series sequencing belongs to the roadmap. |
| What did an earlier increment prove? | [Milestone index](milestones/README.md) | Historical checkpoints and evidence summaries, not current architecture or instructions to start old next steps. |
| Where are raw results/reproduction artifacts? | [Experiment directories](../experiments/) and links from milestones | Acceptance evidence, transcripts, fixtures and reproducible probes. Some platform validation is retained under [infra](../infra/); do not relocate it merely for consistency. |
| How does the conversational agent operate? | [BLAINE.md](../BLAINE.md), [skill convention](../skills/SKILL.md) | Triage, Task skills and conditional policies; not runtime state. |

## Source-of-truth hierarchy

Start with README → architecture or roadmap → the domain's canonical document →
its contracts/accepted ADRs → linked historical evidence. For conflicts, compare
semantic role rather than treating this as a date-based precedence ladder:

- Contracts/policies own normative interfaces and invariants; accepted ADRs own
  architectural rationale. A proposal or older example cannot weaken them.
- Architecture describes current ownership; the roadmap states what is implemented
  and planned, with evidence for the claimed scope. A design decision is not deployment.
- Platform runbooks own actual operational topology/procedure; current runtime reads
  are needed to claim present health. Neither chat nor a historical report supplies it.
- Milestones and experiments preserve what happened, including STOPs and narrower
  proofs. Their historical “current” or “next” text does not direct new work.
- If a contract exceeds an implemented binding, show that gap explicitly (as D2 does).
  If sources genuinely disagree, record the conflict and resolve the smallest scope;
  do not erase evidence or silently treat aspirational behavior as implemented.

## Platform map

| Concern | Source |
| --- | --- |
| Adopted application services, model versions, state paths, prepared D1.G procedure | [Platform services](platform-services.md) |
| Infrastructure components and deployment foundation | [Platform infrastructure](platform-infrastructure.md) |
| Active rootless ownership, normal operation and rollback | [Rootless operations](platform-rootless-docker.md) |
| Actual telemetry coverage and known gaps | [Observability inventory](platform-observability-inventory.md) |
| How credentials reach a running process | [Secret delivery](platform-secrets.md) |
| GPU/vLLM collection and deployment | [GPU/vLLM telemetry](platform-gpu-vllm-telemetry.md) |
| Fleet/Cloud configuration, activation restrictions and recovery | [Grafana Cloud runbook](platform-grafana-cloud.md) |
| Backup/recovery procedures and paused historical work | [Operations/recovery](platform-operations.md), [legacy D1 checkpoint](platform-d1.md) |

## Bounded reconciliation and deferred cleanup

The E0–E3 design pass found and reconciled these navigation ambiguities:

- README repeated platform statuses already maintained in the roadmap/runbooks.
  It now gives concise product orientation and links to those authorities.
- Architecture pointed at a historical product exploration and mixed in D2/D3
  delivery narrative. It now describes current ownership, identifies the Hub design
  as planned, and links implemented scope/status to D2 and the roadmap.
- D3 and new E0–E3 could appear competing milestone programs. The roadmap retains
  D3's meaning and maps the product sequence explicitly; milestone history is intact.
- The legacy D1 page repeated Cloud/service “current” summaries and retained older
  host inventories. Its entry now redirects to canonical platform pages; the old
  checkpoint/procedure text is retained and labeled historical.
- The cognitive-loop research checkpoint combines original proposals with later
  adopted amendments. Its entry now marks this provenance and points to current
  architecture/status without discarding those amendments.

Deliberately deferred: consolidating D1 runbooks/checkpoints into a cleaner file
layout; extracting operational chronology from ADR 0021; normalizing all old ADR
validation labels (including ADR 0004's historical validation note); extracting
still-referenced kernel wire-contract material from the cognitive-loop research
checkpoint; separating D2 usage from its acceptance narrative; and splitting the
long roadmap's architectural summaries from its program status. These overlaps
remain explicit here. They require focused contract/evidence review, not a broad
rewrite inside the Hub design slice.

[Original product exploration](agentic-development-kit.md),
[refactor planning](blaine-refactor-plan.md),
[cognitive-loop checkpoint](research/cognitive-loop-checkpoint.md),
[Multica research](research/multica-carveout.md) and
[Graphify research](research/graphify-carveout.md) remain historical context.
No documentation grants standing host, credential, paid-model, reboot or
publication authorization. Follow the current request and each operation's scope.

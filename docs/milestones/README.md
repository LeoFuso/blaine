# Milestones and evidence

The [roadmap](../roadmap/001-blaine-development-roadmap.md) owns current development
sequencing. Milestones preserve what a bounded run proved, including STOPs and
limitations; their historical “next” instructions do not override that roadmap.

| Program | Latest accepted checkpoint | Evidence |
| --- | --- | --- |
| Track III — Hierarchical Context, Memory & Verified Learning | [III.1 reference research PASS](042-track-iii-1-reference-systems.md); III.2 unstarted | [Source manifest](../../experiments/track-iii-001/evidence/source-manifest.json), [review](../../experiments/track-iii-001/evidence/review.json); source-review scope only |
| Cognitive Kernel 1–12 | COMPLETE: [progress and increment index](cognitive-kernel-progress.md), [Increment 12](037-cognitive-kernel-increment-12-parallel-children.md) | [Parallel children](../../experiments/kernel-increment-12/evidence/summary.json) |
| Frontier boundary | [Increment 11 PASS / CLOSED](036-cognitive-kernel-increment-11-live-pass.md) | [Authorized live probe 002](../../experiments/kernel-increment-11/evidence/live-authorized-002/summary.json) |
| D1.C inference | [Accepted local services, 128k](038-d1-local-inference.md) | [21 checks](../../experiments/d1-service-adoption/evidence/inference-summary.json) |
| D1 platform | [Live service adoption PASS; D1.G pending](039-d1-service-adoption.md) | [Infrastructure validation](../../infra/validation-d1-infrastructure.json) |
| D1 backup | [PAUSED checkpoint](../platform-d1.md); no accepted physical backup/restore | [Volume preservation](../../infra/volume-preparation-d1.json) |
| Worker execution boundary | [Instrumentation and continuation boundary](040-worker-execution-instrumentation.md) | [Evidence summary](../../experiments/worker-execution-instrumentation/evidence/evidence-summary.json) |
| Secret delivery | [ADR 0023](../decisions/0023-runtime-secret-delivery-and-materialization.md) accepted; SecretSpec resolver adopted | [Acceptance](../../infra/validation-secret-delivery.json), [correction spike](../../experiments/secret-delivery-spike/README.md), [runbook](../platform-secrets.md) |
| Jev routing candidate | [Integration PASS; NOT adopted, NOT the default router](041-jev-provider-candidate.md) | [Live authenticated call](../../experiments/jev-provider-carveout/evidence/live/summary.json) |
| D2 Personal Agent | [PASS within documented fixture scope](../daily-driver-d2.md) | [Acceptance](../../experiments/daily-driver-d2/evidence/summary.json), [validation](../../experiments/daily-driver-d2/evidence/validation.json), [post-sync native acceptance](../../experiments/daily-driver-d2/evidence/post-sync-native-summary.json) |

## Planned product milestones

[Personal Agent Hub](../personal-agent-hub.md#milestone-acceptance) defines E0–E3;
these entries are design/navigation references, not new PASS reports.

| Milestone | Target proof | Relationship |
| --- | --- | --- |
| E0 | Workstation connect/doctor/ACP onboarding, portable Linux/macOS/WSL2 design | Consumes D1 availability and D2 controls |
| E1 | Live IntelliJ confined read on a second workstation, same Task after reconnect | D3.A product proof |
| E2 | Bounded remote write/exec and deterministic completion evidence | D3.B capability/effect proof |
| E3 | Java 25 Gradle coding E2E with genuine human response and same-Task resume | Synthetic precursor to D3.C; not full D7 |

Numbered reports in this directory retain earlier architecture/runtime experiments
and kernel progression. Consult the relevant report and its artifacts rather than
inferring live deployment or broader product readiness from a PASS label.

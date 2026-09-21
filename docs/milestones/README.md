# Milestones and evidence

The [roadmap](../roadmap/001-blaine-development-roadmap.md) owns current development
sequencing. Milestones preserve what a bounded run proved, including STOPs and
limitations; their historical “next” instructions do not override that roadmap.

| Program | Latest accepted checkpoint | Evidence |
| --- | --- | --- |
| Cognitive Kernel 1–12 | COMPLETE: [progress and increment index](cognitive-kernel-progress.md), [Increment 12](037-cognitive-kernel-increment-12-parallel-children.md) | [Parallel children](../../experiments/kernel-increment-12/evidence/summary.json) |
| Frontier boundary | [Increment 11 PASS / CLOSED](036-cognitive-kernel-increment-11-live-pass.md) | [Authorized live probe 002](../../experiments/kernel-increment-11/evidence/live-authorized-002/summary.json) |
| D1.C inference | [Accepted local services, 128k](038-d1-local-inference.md) | [21 checks](../../experiments/d1-service-adoption/evidence/inference-summary.json) |
| D1 platform | [Live service adoption PASS; D1.G pending](039-d1-service-adoption.md) | [Infrastructure validation](../../infra/validation-d1-infrastructure.json) |
| D1 backup | [PAUSED checkpoint](../platform-d1.md); no accepted physical backup/restore | [Volume preservation](../../infra/volume-preparation-d1.json) |
| D2 Personal Agent | [PASS within documented fixture scope](../daily-driver-d2.md) | [Acceptance](../../experiments/daily-driver-d2/evidence/summary.json), [validation](../../experiments/daily-driver-d2/evidence/validation.json), [post-sync native acceptance](../../experiments/daily-driver-d2/evidence/post-sync-native-summary.json) |

Numbered reports in this directory retain earlier architecture/runtime experiments
and kernel progression. Consult the relevant report and its artifacts rather than
inferring live deployment or broader product readiness from a PASS label.

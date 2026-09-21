# D1.A/B/D — Actual service adoption and prepared D1.G

2026-09-21: live acceptance PASS, alongside [D1.C](038-d1-local-inference.md).
The five enabled user services use the actual existing runtimes. Same-identity
MIRIX memory and durable Restate Tasks survived controlled restarts. Existing
memory hashes and all five prior D2 Task states remained unchanged. One synthetic
human wait stayed WAITING; another explicitly resumed to COMPLETED. A cognitive
Task retrieved the new MIRIX fact and wrote independently verified artifact bytes.

[Runbook and limits](../platform-services.md),
[evidence index](../../experiments/d1-service-adoption/README.md),
[pre-reboot proof](../../experiments/d1-service-adoption/evidence/pre-reboot.json).

D1.G is prepared, not executed. D1 remains IN PROGRESS. Backup is PAUSED.
No reboot, push, journal deletion, rollback-artifact deletion, sudoers change,
cloud telemetry activation or duplicate runtime was used. Bounded stop recovery
passed, but graceful Hypercorn shutdown did not. This is not general Daily Driver
product acceptance or an S3 migration of the kernel's current ArtifactStore.

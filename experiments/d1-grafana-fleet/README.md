# D1 native Fleet control-plane slice

**STOP for operational activation; accepted local Alloy restored.**

- [Summary](evidence/summary.json): individual acceptance states, including gaps.
- [Native startup failure](evidence/startup-failure.json): unavailable registration
  causes Alloy 1.19.2 initial load failure and start-limit exhaustion.
- [Local restoration](evidence/restored-local.json): exact config, protected BWS
  materialization, native syntax validation, and local three-signal persistence.
- [Authenticated Fleet API inventory](evidence/fleet-api.json): metadata and hashes
  only; no remote configuration contents, credentials or mutations.
- [D1 preserved-state verification](evidence/d1-preserved.json): original object,
  memory and WAITING Task unchanged. No reboot; original evidence files untouched.
- [Security tests](evidence/platform-tests.txt), Ansible scratch/live staging logs.

[ADR 0021](../../docs/decisions/0021-fleet-observability-control-plane.md) separates
accepted architectural direction from failed deployment validation. The
[runbook](../../docs/platform-grafana-cloud.md) records recovery, BWS/Keyring flow,
Cloud delivery gaps and the required future gate. The fixed collector ID is only
proposed; neither enrollment nor remote assignment is claimed. The two inspected
generated pipeline exclusions were never applied after the startup STOP.

The bootstrap token and three Grafana fields were captured only in memory and
passed over stdin to the existing protected writer. The resulting secret file is
outside Git, root-only and not referenced by the active service. No OpAMP runtime,
second collector, installer, custom supervisor, CUDA/model change or sudoers
change was introduced. Backup PAUSED; no push or reboot.

The maintenance TaskSpec is a draft: the accepted kernel has no Fleet/host-
maintenance execution capability, and no fake durable execution was submitted.

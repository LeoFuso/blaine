# D1 service adoption evidence

Resume of the existing D1 work, 2026-09-21. No reboot or push; backup PAUSED.

Accepted live milestones:

- [D1.C inference, all 21 checks](evidence/inference-summary.json).
- [D1.D retained MIRIX identity/content](evidence/mirix-summary.json).
- [D1.B/A preserved legacy and new durable Tasks, controlled restarts, explicit resume](evidence/durable-summary.json).
- [Actual cognitive Task: MIRIX recall to independently verified artifact](evidence/cognition-summary.json).
- [Installed actual ACP client inspection](evidence/acp-interaction.json).
- [Tests, Ansible, systemd and telemetry validation](evidence/validation.json).
- [Prepared pre-reboot evidence](evidence/pre-reboot.json). D1.G is not executed.

[Runbook](../../docs/platform-services.md) includes exact models, versions,
arguments, state/config paths, limits and future verification commands.
Initial/candidate files are historical observations, including failures; they do
not supersede the accepted summaries. No missing evidence is synthesized.

The actual HTTP runtime required systemd's 60-second forced termination during
stop. Recovery and explicit Task resume passed; graceful shutdown is not claimed.
The current ArtifactStore remains local immutable files; the S3 fixture separately
proves object storage. MIRIX semantic memory remains distinct from Restate state.

The original Task request was retained before a binding existed. Later synthetic
Tasks exercise the actual deployed architecture; they do not retroactively turn
that maintenance draft into an executed durable Task.

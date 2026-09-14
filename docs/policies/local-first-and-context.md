# Local-first inference and context

## Deliberate cloud use

Use local tools for retrieval, inspection, filtering, and deterministic transforms.
Local models can spend context on understanding, ranking, and synthesis when useful.
Cloud capability is justified by a material quality benefit: difficult reasoning,
implementation beyond local capability, or independent review warranted by risk.
A local stall is a reason to reassess, not automatic permission to spend.

Before recommending cloud work, establish the reason, permitted data, smallest
useful packet, and a way to verify the result. Apply the TaskSpec's cloud policy
and total budget. Code enforces spend limits and records usage across attempts;
the Personal Agent cannot raise a ceiling or authorize overspend on its own.
No provider or adapter is assumed installed. Worker selection is separate from
whether execution is local or paid cloud; this policy implements no router.

## Just-in-time context

Describe context needs at creation and resolve relevant sources when a step needs
them. Recheck freshness when source changes could alter the result. Keep provenance
(path, revision, query, timestamp, or equivalent) with summaries and extracted facts.
Summaries never outrank original evidence.

For sensitive material, apply configured sharing policy; absent permission, keep it
local and ask only if remote sharing is necessary. Never transmit credentials.
A sanitized derivative still needs an appropriate sharing decision.

## Minimal worker packet

Include only applicable content:

- Objective and requested output.
- Relevant facts and evidence references with freshness/provenance.
- Scope and constraints, including autonomy and cloud limits.
- Completion criteria and expected evidence.
- Uncertainties and unresolved context needs.

Do not send repository dumps, full chat histories, or irrelevant private material.
Do not remove essential dependencies merely to shorten a packet. Prepare related
questions together to avoid repeated cloud context reconstruction.
For independent review, provide the artifact and criteria without a desired verdict
or the builder's persuasive justification. Large context may use
[sharding](context-sharding.md) within runtime-managed work.

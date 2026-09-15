# Local-first inference and context


## Tool before inference

Use the cheapest reliable mechanism that can establish the fact or produce the
result.

Default preference:

1. authoritative or deterministic tools;
2. local model inference;
3. paid cloud inference.

Do not use an LLM to simulate work that a tool can perform directly and
verifiably. Examples include searching files, matching text, parsing structured
data, calculating values, checking network reachability, inspecting Git state,
querying runtime state, or running tests.

The model's role is to decide which tool is appropriate, supply bounded inputs,
interpret the output, and decide what to do next.

This rule applies to local models too. Local inference may be abundant, but it is
still probabilistic and should not replace a cheaper, faster, authoritative
observation.

Escalate from tools to model inference only when interpretation, synthesis,
ranking, classification, planning, or another semantic judgment is actually
required.

When inference is required, prefer local inference. Escalate to paid cloud
inference only when the expected quality or capability benefit justifies the
cost and the Task's cloud policy permits it.

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

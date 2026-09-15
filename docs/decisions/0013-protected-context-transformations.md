# ADR 0013 — Protected context is transformed locally before egress

**Status:** Proposed
**Validation:** Unvalidated

## Context

Blaine may operate across projects and sources with different confidentiality,
sharing, and data-handling requirements.

Some local context may be safe to send to an allow-listed cloud worker.

Other context may be allowed to leave the machine only after transformation.

Some context must remain local regardless of cloud authorization.

Examples of potentially protected information include:

- private project or namespace names;
- internal identifiers;
- source-code symbols;
- repository paths;
- hostnames;
- customer or tenant references;
- operational logs;
- credentials or secrets;
- data whose sharing policy differs by project.

Cloud authorization alone is therefore insufficient.

Blaine needs to distinguish:

- whether context may leave the local trust boundary;
- what transformation, if any, is required before egress.

These are separate decisions.

## Decision

Protected-context handling occurs locally before context is eligible for external
egress.

Blaine separates:

1. egress authorization;
2. context transformation.

A useful initial classification model is:

- `PUBLIC` — safe to share according to normal policy;
- `CLOUD_ALLOWED` — eligible for authorized cloud use without mandatory
  identity transformation;
- `PSEUDONYMIZE` — eligible only after required local transformation;
- `LOCAL_ONLY` — must not cross the local trust boundary.

These categories are conceptual and may evolve.

`LOCAL_ONLY` always overrides cloud authorization or broad-context approval.

A `PSEUDONYMIZE` classification means:

> If this context is otherwise authorized for egress, transformation is
> mandatory.

It does not mean:

> Transformation itself grants permission to send the context.

## Transformation

Transformation should preserve the semantic structure needed for the external
worker while removing or replacing protected identities where required.

For example, a protected identifier may be transformed locally from:

`private_namespace.AuthorizationService`

into a stable token such as:

`NAMESPACE_01.SERVICE_07`

The external worker receives only the transformed representation.

Any reversible mapping remains local.

The exact token format is an implementation concern.

## Hashing versus pseudonymization

Hashing and reversible pseudonymization solve different problems.

A one-way hash may be appropriate when Blaine only needs stable comparison or
deduplication.

A one-way hash cannot support local reconstruction of an external worker's
response.

When Blaine needs to send transformed context and later restore local identities,
it requires reversible local tokenization or pseudonymization rather than plain
hashing.

The mapping must not be included in the external context packet.

## Referential consistency

Transformations must preserve referential consistency within the relevant
context boundary.

If the same protected symbol appears several times in a Cloud Context Packet, it
should normally receive the same pseudonym within that packet or applicable
mapping scope.

This allows an external worker to reason about relationships without learning
the protected identity.

The scope and lifetime of mappings are intentionally unspecified for now.

Possible scopes may include:

- one cloud invocation;
- one Task;
- one project;
- another explicitly controlled scope.

The safest useful scope should be preferred.

## Transformation modes

Not all context should be treated identically.

Future preparation may support operations such as:

- preserve exact;
- redact;
- pseudonymize;
- summarize;
- omit.

The appropriate transformation depends on both policy and the semantic purpose
of the context.

For example:

- a secret should normally be omitted;
- a protected namespace may be pseudonymized;
- an implementation body may need to remain exact;
- irrelevant neighboring context may be omitted;
- an architectural description may be safely summarized.

Context transformation must not silently damage the evidence required for the
task.

## Code and structured data

Source code is more difficult to transform safely than ordinary prose.

Protected information may appear in:

- package names;
- class names;
- method names;
- imports;
- string literals;
- configuration;
- stack traces;
- file paths;
- generated identifiers.

Transforming these elements may reduce semantic quality or break structural
relationships.

Therefore protected-code transformation should be purpose-aware.

Blaine should prefer the minimum transformation necessary to satisfy policy
while preserving the external worker's ability to reason about the selected
context.

This ADR does not define a universal source-code sanitizer.

## Relationship to Cloud Context Packet

ADR 0009 defines the Cloud Context Packet as the mandatory cloud context
contract.

Protected-context processing occurs before protected elements are eligible for
inclusion in that packet.

Conceptually:

local sources
-> context discovery and selection
-> classification
-> required local transformation
-> Cloud Context Packet
-> Cloud Dispatch Boundary
-> external worker

The packet may record that transformations occurred without exposing the private
mapping itself.

A broad-context override does not bypass protected-context policy.

## Relationship to cloud authorization

ADR 0008 governs paid-cloud dispatch authorization.

The authorization decision answers:

> May this cloud invocation occur?

Protected-context policy answers:

> Which information may leave, and in what representation?

These gates must remain independent.

For example:

cloud allowed
+
context LOCAL_ONLY
=
context does not leave the machine

and:

cloud allowed
+
context PSEUDONYMIZE
+
successful required transformation
=
transformed context may be eligible for the Cloud Context Packet

## Non-cloud consumers

The same trust-boundary concept may eventually apply to external tools or
services that are not paid cloud models.

Examples may include:

- third-party hosted APIs;
- external analysis services;
- untrusted or differently trusted agents;
- remote execution environments.

This ADR is motivated by cloud-agent egress but should not require every future
external consumer to be treated identically.

Trust and policy remain explicit.

## Ingress and rehydration

An external worker may return content containing pseudonyms.

Where local reconstruction is required, Blaine may rehydrate the response using
the locally retained mapping.

Rehydration happens inside the local trust boundary.

External workers must not receive the private mapping merely to simplify
response handling.

Rehydration must not be treated as proof that the returned content is correct or
safe.

Normal verification still applies.

## Boundaries

This decision does not:

- authorize cloud usage;
- define the final classification taxonomy;
- require pseudonymization for all private data;
- make secrets safe to send;
- require one mapping scope for every workload;
- define a production cryptographic design;
- define a universal source-code transformer;
- replace Cloud Context Packet preparation;
- replace source-level permissions;
- make transformed context automatically shareable;
- require implementation before a real protected-context workload exists.

## Consequences

Blaine gains a clear architectural distinction between cloud authorization and
data egress policy.

Protected project identities may eventually be concealed while preserving enough
structure for external reasoning.

Cloud Context Packets can enforce sharing constraints before dispatch.

Broad-context overrides remain bounded by non-bypassable local restrictions.

The system gains complexity around classification, mapping, transformation, and
rehydration.

Source code in particular may require domain-aware transformation.

Because that complexity is substantial and not currently the highest-priority
Blaine capability, implementation should remain incremental and driven by real
protected-context workloads.

## Validation

### Hypothesis

Blaine can transform selected protected identities locally, expose only the
transformed representation across an external boundary, and reconstruct returned
references locally without leaking the protected mapping.

The transformation must preserve enough referential structure for meaningful
external reasoning.

### Validation level

Isolated.

### Minimal validation

Create a synthetic fixture containing:

- a protected project or namespace;
- several repeated protected symbols;
- public context;
- one `LOCAL_ONLY` value;
- one secret-like value that must be omitted;
- code or structured text containing relationships between protected symbols.

Apply a simple local transformation into stable pseudonyms.

Construct a fake Cloud Context Packet and pass it to a fake external worker.

Have the fake worker return a response using the pseudonyms.

Rehydrate the response locally.

No real private project data should be used.

### Evidence

PASS requires demonstrating that:

- protected cleartext identifiers are absent from the external payload;
- repeated protected identifiers receive consistent pseudonyms within the chosen
  mapping scope;
- `LOCAL_ONLY` data never appears in the external payload;
- secret-like fixture data is omitted rather than merely renamed;
- the private pseudonym mapping remains local;
- the fake external response can be rehydrated locally;
- structural relationships between transformed identifiers remain understandable;
- cloud authorization and transformation decisions remain separate;
- a broad-context override cannot expose `LOCAL_ONLY` fixture data;
- transformation does not require a real cloud provider.

The validation should also record any meaningful semantic degradation caused by
transforming code or structured context.

### Not required for validation

- real confidential project data;
- production cryptography;
- Codex or another real cloud worker;
- paid cloud usage;
- Restate integration;
- automatic classification of every source;
- a universal code sanitizer;
- persistent project-wide mappings;
- training or fine-tuning;
- implementation before a real workload justifies it.

### Reconsider when

Reconsider this decision if:

- pseudonymization consistently destroys the semantic quality required by cloud
  workers;
- source-level access control makes transformation unnecessary for real
  workloads;
- protected context is better handled entirely through local inference;
- operational complexity of reversible mappings exceeds their practical value;
- a stronger trust-isolation mechanism can satisfy the same requirements more
  simply.

The default response to difficult-to-transform protected data should be to keep
it local, not to weaken the egress boundary.

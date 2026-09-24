# III.10 predeclared experiment protocol

Frozen before execution: [cases](cases.json), [trusted state](state.json),
[security canaries](security.json), [machine protocol](protocol.json), and their
[hashes](evidence/fixture-freeze.json). Exactly four cases per LOCAL_HANDOFF,
CHECKPOINT_RESUME and SECOND_PROCESS group; no inference or network.

The independently trusted receiving route is execution-main. A reference naming a
known execution is not a credential. The harness owns current state files and the
route/participant; a caller controls only the serialized envelope/claims. No caller
can select the state file, route, role or mutation. This is an offline trust assumption,
not production authentication. Every operation reconstructs a fresh binding.

III.2's unchanged ContextTree validates the complete structure before lineage use.
III.10's minimal read adapter intersects that lineage with current trusted entry
classification, domain grants and policy exclusions. It accepts the already established
four origin/status pairs. It neither admits new verified learning nor calls promotion;
those gates remain separate. Old experimental opaque tokens are never serialized.

| Case | Expected receiving result |
| --- | --- |
| A1 | SUCCESS; cognition, worker and verifier see exactly the same five entries. |
| A2 | SUCCESS; forged scopes/domain/authority and trace do not expand those five. |
| A3 | SUCCESS; observation stays unverified and failure stays verified failure. |
| A4 | DENIED; known foreign context is not the trusted route's context. |
| B1 | SUCCESS; independently loaded checkpoint retains the same five entries. |
| B2 | SUCCESS; current P2 removes old-rule despite its presence in historical packet. |
| B3 | SUCCESS; current T2 replaces old-rule with new-rule after reparenting. |
| B4 | INVALID_CONTEXT; missing reference never falls back to serialized scopes. |
| C1 | SUCCESS; separate receiving OS process sees the same five entries. |
| C2 | SUCCESS; separate receiver ignores forged scope/authority. |
| C3 | SUCCESS; current P2 wins over serialized P1 policy snapshot. |
| C4 | UNAVAILABLE; previous successful transfer cannot replace missing current evidence. |

The five baseline IDs are failure, observation, old-rule, public-rule and success.
A domain-private entry also lives structurally at root: security is independent of
ancestry. Sibling, descendant and foreign-domain entries remain hidden. Source audit
logs and binding-evidence IDs never enter ordinary retrieval or denial diagnostics.

Checkpoint writers execute as separate processes, persist reference plus a historical
packet, and exit. Receivers then load serialized material and a current trusted-state
snapshot independently. Process groups use actual Popen/exec, with child PID/parent PID
attestation retained privately. Machine stdout contains only the complete bounded
response; stderr must be empty. Dynamic PIDs are not expected to reproduce byte-for-byte.

No global revision/activity counter is exposed. Trace and parent-operation references
propagate as bounded non-authoritative correlation values. Known historical policy and
topology references identify fixture revisions, never confer old grants or lineage.
Same-state replay must match exactly; changed state must be re-evaluated.

Supplemental probes (not additional primary cases) cover current-only writes and later
process re-query, parent/descendant write visibility, direct IDs, empty queries,
malformed JSON/duplicate keys/references, hidden structural corruption, unavailable or
invalid policy, and forced packet saturation. Stable ID ordering selects whole entries
within **2048 UTF-8 bytes for the complete JSON response, including stdout newline**.
Diagnostics, receipt, partial marker and provenance all count. No cache is introduced.

All expected primary results are fixed before evaluation. Mandatory isolated controls
trust serialized scope or stale policy; each must produce actual forbidden content and
metadata plus checker exit 1. An additional control trusts serialized provenance and
must produce an actual status elevation plus checker exit 1. Default execution is
restored and byte-compared after controls. No thresholds change after observation.

The independent checker reads retained output, recomputes exact visibility/provenance,
checks full serialized bytes, uses scope-specific literal scans, verifies process
attestations and checks fixture/source pins. Privileged input/audit records are clearly
separate from exports; legitimately permitted P1 output is checked under P1, while
receiving P2 output must exclude its former entry. Every externally visible projection
is scanned, not only memory content. Historical Track III evidence remains unchanged.

PASS requires every primary oracle, both mandatory real leakage controls, provenance
preservation, exact current-policy/topology/replay semantics, 2 KiB bounds and zero
forbidden content/metadata. No production concurrency, durability, revocation latency,
transport or authentication claim follows from this finite fixture.

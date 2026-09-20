# Increment 5 — HumanDecision contract gate BLOCKED

Historical stop, resolved by explicit user approval of the scoped verifier.
See [Increment 5 PASS](011-cognitive-kernel-increment-5-passed.md).

Increment 4 passed with retained live evidence. The user's clarification permits
conditional progression, so the next bounded objective was checked: a joined
HumanDecision child accepts a scoped YES or NO through a controlled interaction,
waits durably, verifies the response and returns a bounded result to its parent.

## STOP REPORT

- **Expected:** either valid human answer can satisfy the same accepted child
  completion contract; cognition cannot fabricate approval. Invalid, duplicate or
  stale responses cannot establish completion or wider authority.
- **Observed:** current `CompletionCriterion` accepts exactly `{artifact, sha256}`
  and the verifier checks that one digest. A spec accepting exact YES rejects NO.
  Multiple criteria are conjunctions, not alternatives. There is no registered
  human-response verifier. Strict validation rejects an unapproved alternative-
  digest field and an inline `TaskResult.decision` field. The latter could instead
  be represented by a bounded referenced artifact, but no such response-evidence
  validation contract is currently defined.
- **Architecture impact:** local contract/verifier extension would be required;
  none applied. No contradiction in the approved Task-scoped loop. Increment 4
  and all earlier passed increments remain intact.
- **What was attempted:** read the existing completion, result, capability and
  WAIT contracts; run one deterministic completion/result counterexample. No
  human capability, transport, runtime handler, kernel or contract was changed.
  No live human acceptance probe or new inference was run.
- **Unresolved question:** what exact evidence links an authenticated, scoped
  YES/NO response to completion while accepting either answer? A preselected
  expected answer weakens the requirement; a generic marker written by cognition
  does not prove a human decision.
- **Exact human decision required:** approve a narrow scoped human-response
  verification contract and its bounded result representation before implementation.
- **Safest next option:** authorize a small additive verifier for a versioned
  human-response artifact (decision, request/Task scope and response identity),
  with deterministic validation independent of cognition, returned by artifact
  reference in TaskResult. Settle its binding to controlled input before coding.
  Do not silently add an OR-of-digests shortcut or substitute worker claims.

This is the mandatory semantic-change gate, not a failed earlier test or a claim
that human decisions are incompatible with Blaine. A trusted capability receipt
could be another design, but choosing its authority/evidence semantics without
review would evade the gate. No speculative implementation was added.

Reproduce the counterexample with the existing Python environment:

```sh
python experiments/kernel-increment-5/contract_probe.py experiments/kernel-increment-5/evidence
```

[Machine-readable evidence](../../experiments/kernel-increment-5/evidence/summary.json).
Next increment remains **5**, pending the narrow decision. No Increment 6+ work.

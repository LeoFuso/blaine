# Increment 5 — scoped HumanDecision PASS

Hypothesis: a joined child can obtain any allowed human answer through a controlled
input boundary, wait durably, and return exact independently verified response
evidence without giving cognition approval authority. The user explicitly approved
the narrow contract/verifier extension after the recorded contract-fit stop.

## Implementation

`HumanDecisionRequest` is a version-1 JSON envelope containing child Task identity,
originating Task identity, request ID/revision, bounded question and allowed string
set (1–8 choices). `HumanDecisionResponse` binds Task, request ID/revision, digest
of the complete request, response identity and selected value. No answer has special
kernel meaning. A test also accepts DEFER from a different allowed set.

The additive completion evidence variant is `{artifact, verifier: human_response,
request: <accepted request envelope>}`. Existing `{artifact, sha256}` remains intact.
The verifier checks exact artifact bytes, response scope/version/value and the
runtime's accepted-input reference. Cognition cannot manufacture that reference
by writing an artifact. TaskResult stays unchanged and returns response/request
artifact refs plus verifier evidence; no transcript or unverified inline answer.

`human.request` publishes the immutable request for the controlled input adapter.
Policy checks its accepted scope and capability grant. WAIT's additional bounded
input type `human_response` uses the existing one-shot Restate workflow promise.
The shared `submit_human_response` handler validates input before resolution; the
main workflow consumes it, retains the exact response and owns state transitions.
The typed wait does not accept the generic text input handler. Child request scope
must match the parent and deterministically derived child identity.

This is a controlled local transport test, **not an authenticated public UI or a
real person's approval**. An eventual external transport must establish the actor
before calling the trusted input binding. No response grants global authority or
changes capability grants. No notification, chat, email or Board operation exists.
No LLM determines validity; this increment uses scripted semantic decisions.
Model schema guidance was extended to describe these approved contracts; JSON-only
generation and strict parsing/validation behavior were not changed.

## Gate evidence

- YES and NO each independently completed a joined HumanDecision child and parent.
  Each child result is 701 bytes; parent receives bounded refs, not child history.
- Sixteen live negative controls: disallowed value, wrong Task, wrong request,
  stale revision/digest, unsupported version, missing field, duplicate completed
  response, for each answer. Invalid inputs leave the wait unchanged.
- Premature COMPLETE fails for each child. Child success alone also fails the
  parent's independent completion; its own exact artifact is required.
- One runtime SIGKILL and one Restate server SIGKILL while parent/child wait.
  Identities and states match after restart; persisted journal prefixes match
  byte-for-byte. Each child publishes one request and runs four cognitive turns,
  with no replay duplication. Response artifact digests remain valid.
- 30 focused tests pass. All seven original Increment 1 live cases and the original
  joined-child recovery probe pass against the extended implementation.

[Summary](../../experiments/kernel-increment-5/evidence/approved-extension/summary.json),
[live controls](../../experiments/kernel-increment-5/evidence/approved-extension/acceptance/negative-controls.json),
[replay verification](../../experiments/kernel-increment-5/evidence/approved-extension/replay-verification.json),
[tests](../../experiments/kernel-increment-5/evidence/approved-extension/tests.txt).

Reproduce: existing runtime Python runs `scripts/verify-kernel-human.py` with
`--restate-server` pointing to the pinned executable and a fresh `--output` path.
No installation, shared-service changes or secrets are needed.

Changed: `contracts.py`, `execution.py`, `workflow.py`, model schema guidance;
new `human.py`, focused tests and live probe. Exact artifact store, memory provider,
loop algorithm and TaskResult representation remain unchanged. This is the
authorized extension, not an unapproved architectural deviation.

All conditional progression gates pass. Exact next increment: **6**, one bounded
YouTrack capability, preserving Card/Task separation and policy admission.

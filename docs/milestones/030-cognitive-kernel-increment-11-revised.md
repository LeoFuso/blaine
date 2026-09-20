# Increment 11 — revised isolated frontier boundary

**2026-09-20 — PASS, isolated proof only. STOP before live preflight/dispatch.**

Hypothesis: heterogeneous workers can retain strict Task/context/scope/provider
and execution authority while economic suitability and observed token/cost usage
remain separate. One worker dispatch need not equal one underlying model request.
The user explicitly authorized this architectural correction after the live
preflight exposed unrealistic universal token/request/dollar requirements.

## Implemented correction

[Frontier v2 contract](../contracts/frontier-dispatch.md) is the current reference.
`FrontierAuthority` and `AuthorizedFrontierRequest` are version 2; old grants are
not silently migrated. No kernel, Task/NextAction, PolicyGate, CompletionContract,
verifier, HumanDecision, MIRIX, worker or ExecutionEvent semantics changed.
Their [before/after hashes](../../experiments/kernel-increment-11/evidence/revised/authority-integrity.json)
match exactly.

Hard authority retains Task identity, exact approved bindings/destination,
immutable context/digest, scope subsets, trusted approval, deadline, dispatch
slots and replay identity. Global disable/kill switch and external account-status
inputs can deny dispatch independently of suitability. Account ceiling integration
is absent, explicitly `not_configured`; exhausted/unknown controls are fixtures.

Economic routing uses ADR 0010 capability/quality requirements. Scripted assessments
are UNDERPOWERED, JUST_RIGHT or OVERKILL. The router chooses an adequate authorized
candidate using sufficient-local preference and ordinal expected cost-to-success.
An explicitly selected OVERKILL worker remains legally admissible. No sufficient
authorized candidate returns STOP_OR_ESCALATE. No prices or learned reliability
are invented. A classifier may later change without changing authority/runtime.

Observed usage is separately stored by dispatch identity: worker/provider/model,
observed producer/session, available model-call identities/counts, input/output
tokens, cost, runtime and outcome. Verification and final outcome correlate through
existing Task/event references. Unknown values stay unknown. No usage observation
can increase or reset dispatch allowance.

Universal hard model-request, token and dollar ceilings are removed as baseline
requirements. The v1 invocation allowance becomes explicitly worker-attempt slots
in `max_dispatches`; it never claims to count underlying model HTTP requests.
Completed effects are counted, not provisionally priced.
Token/model-call/cost fields remain available as soft hints, optional explicitly
required binding-native controls, and observed accounting. Missing required native
support denies admission. No fabricated maximum-token/dollar charge is recorded.

Core code is vendor-neutral. Synthetic candidate bindings represent Goose/Qwen,
Codex/economical or strong, and Junie/Claude. No such worker was invoked here.
Only the fixed local synthetic provider process executed.

## Tests and native acceptance

Baseline: 96 focused tests passed before the correction. Revised suite: **98 passed**,
including all prior kernel modules. Eleven frontier tests replace the nine v1 tests;
the previous 87 tests remain intact. Native proof: **19 Tasks**, **356 valid events**,
**4 synthetic provider invocations** (2 executed, 1 confirmed non-execution,
1 timeout/unknown). All accepted test-result digests independently verified.
A Task completing its expected denial/timeout report is not cloud work succeeding.

| Gate | Evidence/result |
|---|---|
| A disabled | All frontier candidates denied; no provider calls |
| B provider/model | Wrong provider/model rejected before execution, independent of suitability |
| C scope | Read/write escalation denied |
| D adequate economical | JUST_RIGHT economical candidate selected over UNDERPOWERED local and OVERKILL stronger |
| E stronger OVERKILL | Not preferred at ordinary rank, but independently authorized if explicitly selected |
| F cheap UNDERPOWERED | Higher requirement selects stronger adequate candidate |
| G none adequate/authorized | STOP_OR_ESCALATE; no unauthorized fallback |
| H global/account | Disable, kill switch, exhausted account and unknown configured status deny |
| I observed usage | One synthetic dispatch reports 3 model calls, 120/30 tokens despite soft 1/1 hints; cost unknown; no enforcement claim |
| J replay | Committed effect survives SIGKILL/restart; provider runs once, settlement/accounting once |

Additional controls cover approval, exact context, deadline/runtime, repeated
attempt beyond dispatch slots, missing required native guarantee, unknown outputs,
observed binding mismatch and native-control violation. Provider observations from
violations are retained without authorizing success. A synthetic monetary value
is tested only as accounting; no pricing or actual cost is claimed.

Recovery killed runtime PID 298867 after the committed worker result and before
settlement; replacement PID 298967 replayed the same journal. Provider request
identity `dispatch:authorized/2`, session identity, persisted grant and capability
result remain correlated. One accounting record and one settlement follow recovery.
Timeout holds its slot and unknown usage without retry. The test does not prove
remote exactly-once execution during response loss before a journal commit.

The first revised native run exposed a probe instrumentation error: usage emitted
`capability.finished/recorded`, which existing event validation correctly discarded.
Only that probe label was corrected to existing success/failure. The captured
[counterexample](../../experiments/kernel-increment-11/evidence/revised/instrumentation-counterexample/diagnosis.json)
is retained. Final native acceptance includes usage events and independent artifact
checks; no validation was weakened.

## Reproduction and evidence

```sh
PYTHONDONTWRITEBYTECODE=1 /home/leofuso/workspace/blaine/.local/runtime-venv/bin/python -m unittest discover -s tests -p 'test_kernel*.py'
PYTHONDONTWRITEBYTECODE=1 /home/leofuso/workspace/blaine/.local/runtime-venv/bin/python experiments/kernel-increment-11/probe.py --output /tmp/blaine-frontier-v2-FRESH --restate-server /home/leofuso/workspace/blaine/.local/bin/restate-server
PYTHONDONTWRITEBYTECODE=1 /home/leofuso/workspace/blaine/.local/runtime-venv/bin/python experiments/kernel-increment-11/verify.py /tmp/blaine-frontier-v2-FRESH/evidence
```

The output path must not exist. Native probe uses temporary loopback services only;
all its processes are stopped on exit. No model service, secrets or host settings
are changed. No model inference occurred.

- [Summary](../../experiments/kernel-increment-11/evidence/revised/summary.json)
- [Independent gate](../../experiments/kernel-increment-11/evidence/revised/acceptance/verification.json)
- [ExecutionEvents](../../experiments/kernel-increment-11/evidence/revised/acceptance/events.jsonl)
- [Focused test results](../../experiments/kernel-increment-11/evidence/revised/focused-tests.txt)
- [Restate recovery](../../experiments/kernel-increment-11/evidence/revised/acceptance/recovery.json)
- [Historical v1 source snapshots](../../experiments/kernel-increment-11/evidence/revised/before/)

Changed implementation: `runtime/kernel/frontier.py`, new `worker_routing.py`,
`tests/test_kernel_frontier.py`, Increment 11 `probe.py` and `verify.py`.
Documentation: frontier contract, this milestone and progress index. Prior v1
milestone/evidence remains historical rather than retroactively relabeled v2.

## Exact next decision and limits

Stop here. No cloud call, credential inspection, live preflight or Increment 12.
A smallest next live proof is one read-only worker dispatch with the tiny synthetic
ORCHID/7319 artifact and deterministic result verifier, exact approved binding and
destination, enforced short runtime, no automatic retry, and recorded usage where
available. It may contain multiple underlying model calls. Missing exact token or
dollar enforcement alone no longer blocks it unless the Task explicitly requires
those guarantees.

Human authorization should name the real binding/model/destination, scope, deadline,
current global/account guardrails and approval. A binding-specific preflight must
still establish destination/scope enforcement and the unknown-outcome strategy.
Existing Codex/gpt-6-astra is only a candidate from earlier non-secret evidence;
no new provider readiness claim is made here. Real egress/sandbox/cancellation and
remote usage remain unverified. Do not infer cloud authorization from this PASS.

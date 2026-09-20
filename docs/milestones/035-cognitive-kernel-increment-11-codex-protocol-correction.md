# Increment 11 — Codex 0.155.1 normalization correction

**2026-09-20 — PASS, offline correction only. Increment 11 remains open.**

The installed package is Codex CLI 0.155.1; its executable SHA-256 still matches
the binary inspected in milestone 034. The user supplied authoritative semantic
definitions from [OpenAI Codex tag `rust-v0.155.1`, `codex-rs/exec/src/exec_events.rs`](https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/exec/src/exec_events.rs).
That resolves the prior offline semantic-evidence STOP. The source was not fetched
again; the captured provenance explicitly distinguishes supplied definitions from
local package/binary verification. Revalidate these rules on any CLI upgrade.

## Binding correction

| Codex event | Old adapter | Corrected binding |
|---|---|---|
| `turn.completed` | Usage only; optional for acceptance | Required successful terminal marker |
| `turn.failed` | Fixed omission label, not a rejection condition | Terminal failure; no successful result admitted |
| Top-level `error` | Fixed omission label, not a rejection condition | Unrecoverable/fatal terminal failure |
| Completed item of type `error` | Unexpected item, always rejected | Non-fatal diagnostic, compatible with terminal success |
| Valid text without terminal event | Could succeed | Unknown/incomplete; rejected |
| Contradictory/duplicate terminal markers | No consistency check | Unknown; rejected without optimistic precedence |
| Unknown/malformed event | Could be ignored or lose observation | Rejected with bounded structural observation |

The existing one-shot invocation, projection/digest checks, immutable grant,
deadline, cancellation and exclusive receipt are unchanged. The new pure
`observe_stream` function is local to the Codex binding; no Codex vocabulary enters
Task lifecycle contracts. Acceptance additionally requires exactly one valid bounded
result, valid session identity, zero exit, no timeout/cancellation, no unsupported
effect item, and no unknown/malformed event. Content after terminal completion is
rejected conservatively for this one-turn binding. No broader upstream ordering
guarantee is claimed.

Strict output JSON validation still rejects missing/duplicate/extra result fields;
there is no model-output repair. A successful normalized result remains only a
worker candidate. The existing capability/artifact admission and CompletionVerifier
decide whether it satisfies the Task. Tests demonstrate protocol success without
evidence cannot complete, admitted exact content can verify, and different required
content still fails verification.

## Safe observations, not unrestricted error capture

Observation v2 preserves sequence numbers, known upstream event/item kinds,
bounded protocol-shaped item IDs, result presence, terminal status, binding-owned
classification/provenance, usage and explicit rejection categories. Errors are
classified from the pinned protocol, never from their message or an extra
model-supplied `terminal` flag. Unknown discriminator strings and extra fields are
not copied into evidence.

Error message **presence and UTF-8 byte length** are retained alongside a fixed
sanitized representation. All arbitrary diagnostic text is omitted: no prefix,
raw hash, credentials, headers, tokens, session secrets or private context are
copied. This is a deterministic structure-only policy, not a claim that regex
redaction or semantic sensitive-data detection is solved. Private reasoning,
raw assistant text and stderr are also absent from the observation. Successful
validated candidate output uses the existing result artifact path.

This preserves the information needed to distinguish diagnostic/non-terminal
items from fatal events and to inspect ordering and rejection. It deliberately
does **not** preserve arbitrary human-readable provider root-cause messages.
Malformed streams produce a safe observation instead of failing before capture.
Bounds are 256 KiB stream, 128 records and 32 KiB per parsed record; exceeding them
rejects without retaining arbitrary stream contents.

The provider-neutral result DTO is unchanged. The offline live-evidence verifier
understands observation v2 while retaining the original legacy interpretation for
milestone 033. Unsupported observation versions are rejected.

## Reservation and historical integrity

Worker terminal status and the frontier effect ledger are separate. A known
terminal worker failure does not establish that the provider performed no work.
The current invocation boundary treats rejected adapter results as unknown effect
outcomes; existing pending-reservation behavior therefore remains conservative.
Success uses existing idempotent successful settlement; failure/unknown does not
refund a slot or authorize another dispatch. No new settlement state was added.

Milestones 033 and 034 and all prior Increment 11 evidence remain byte-for-byte
unchanged. `frontier-live-binding-001` remains FAILED, with no admitted result and
one pending UNKNOWN dispatch reservation. The original error ordering/body remain
unrecoverable. New fixtures place a synthetic error both before and after the
answer; neither is claimed to reconstruct the lost original ordering.

## Offline validation

- 12 updated correction tests cover 14 synthetic stream cases. Process creation
  is mocked; network connections are forbidden by the fixture. Zero inference.
- 27 focused frontier tests pass, including seven additional binding controls for
  error confidentiality, malformed/unknown inputs, terminal conflicts, strict
  result validation, independent artifact completion and unchanged settlement.
- 3 worker tests pass; the broader Cognitive Kernel suite passes **114 tests**.
- Independent historical verifiers: Increment 10 PASS (28 events), Increment 11
  projection PASS (434 events), original live STOP preserved (74 events).
- Kernel source and historical evidence hashes match the pre-correction snapshot.
- `git diff --check` passes. No cloud/provider calls, new dependencies, secret
  inspection, serving changes or other-worktree edits.

Changed scope: experimental Codex binding and its offline verifier, existing
diagnostic fixture/controls, focused tests, binding documentation, progress and new
evidence. Task lifecycle, Restate, PolicyGate, CompletionContract/Verifier,
SemanticDecisionProvider, frontier authorization, economic routing, projection,
AuthorizedFrontierRequest and replay semantics are unchanged.

## Proposed next live probe — not executed

The adapter is ready for one newly authorized live binding probe, subject to the
same concrete preflight. Prepare a **fresh** fixture with Task
`frontier-live-binding-002`, dispatch `dispatch:frontier-live-binding-002/2`, fresh
output/receipt, and the existing synthetic ORCHID/7319 → FLOWER/MASKED_01 projection.
Authorize its exact projected digest, one read-only sterile Codex 0.155.1 dispatch
with gpt-6-astra intent, the established OpenAI/ChatGPT boundary, and a 60-second
deadline. Do not reuse the existing probe's historical Task constant/receipt.

Use corrected event normalization and safe diagnostics, then the existing exact
artifact verifier and settlement path. No Blaine retry, replacement, fallback or
escalation; internal provider behavior remains separately observable or UNKNOWN.
Any failure stops the new probe. This proposal is not authorization to execute it.
Increment 12 remains unstarted.

## Evidence

- [Summary](../../experiments/kernel-increment-11/evidence/codex-01551-correction/summary.json)
- [Version/source provenance](../../experiments/kernel-increment-11/evidence/codex-01551-correction/protocol.json)
- [Synthetic cases and ordered observations](../../experiments/kernel-increment-11/evidence/codex-01551-correction/cases.json)
- [Correction tests](../../experiments/kernel-increment-11/evidence/codex-01551-correction/correction-tests.txt)
- [Kernel tests](../../experiments/kernel-increment-11/evidence/codex-01551-correction/kernel-tests.txt)
- [Unchanged historical/kernel hashes](../../experiments/kernel-increment-11/evidence/codex-01551-correction/integrity.json)

**PASS for the offline correction only. STOP before another live dispatch.**

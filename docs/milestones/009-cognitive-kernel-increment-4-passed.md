# Increment 4 — MIRIX semantic context PASS

The existing ContextProvider seam supplies bounded MIRIX semantic memory to the
unchanged JSON-only Qwen adapter and Cognitive Loop. Real local acceptance passed
all three cases; all 27 focused unittest cases pass. The earlier binding blocker
is resolved by user-supplied `client-df3da0d9` / `probe-leofuso`.

| Case | Live observation | Verified result |
| --- | --- | --- |
| Fresh-process recall | Seed process 221898 exited; runtime process 222321 retrieved `sem_MFYP`. `VIOLET_7429` occurs in memory, not the accepted objective. Qwen selected artifact.write with that exact value. | COMPLETE admitted only after exact artifact digest verification |
| Absent memory | MIRIX embedding search returned zero items for the unseeded experiment fixture. Qwen followed the Task's explicit fallback. | Exact `FALLBACK_5281` artifact; COMPLETED |
| Conflict | Retrieved `sem_DTLG` says `OLD_RED_1938`; current Task requires `CURRENT_GREEN_6204`. Both provenance classes reached Qwen. | Qwen wrote current value; exact verifier satisfied. Subsequent turn retained both artifact provenance and conflicting memory. |

Each Task took two live Qwen turns: INVOKE_CAPABILITY → COMPLETE. Three allowed
artifact writes occurred. Raw provider content, strict validated decisions,
deterministic PolicyGate evaluations, capability receipts, completion evaluations,
Task identities, Restate journals and exact artifact snapshots are retained.
No synthetic response is counted as live inference.

## Components and provenance

- Cognition: six `POST http://127.0.0.1:8000/v1/chat/completions` calls; captured
  request and response model `Qwen/Qwen3.5-9B`, vLLM. 10,774 prompt tokens and 316
  completion tokens. Maximum complete CognitiveTurn packet: 2,563 bytes.
- Memory: `GET http://127.0.0.1:8531/memory/search`, `search_method=embedding`,
  semantic/details only, limit two, fixed distance threshold 0.5, experiment tags.
  Six runtime queries; maximum selected memory context 842 bytes, empty case two
  bytes (`[]`). This demonstrates bounded retrieval in a controlled fixture
  scope, not relevance quality across an entire personal-memory corpus.
- Embedding: persisted MIRIX agent selects `BAAI/bge-m3`, dimension 1024,
  `hugging-face` endpoint type at `http://127.0.0.1:8001/v1`. Native source inspection
  shows embedding search calls that configured embedding client. Configuration,
  live API responses and the source path establish provenance; internal raw BGE
  HTTP exchanges/token usage were **not** captured.
- Seeding: exactly two explicit `POST /memory/add_sync` calls, followed by two
  embedding readbacks verifying exact marker preservation. MIRIX uses its
  existing Qwen configuration for extraction. Its internal extraction-call count
  is not captured and is not included in the six CognitiveTurn calls. No automatic
  ingestion exists. The two tagged experiment memories remain in MIRIX.
- Application code owns JSON validation, policy, execution, lifecycle, artifact
  digests and completion. MIRIX supplies data only. All 11 recorded Increment 3
  source hashes remain unchanged; no service/configuration/secret changes.

New files: `runtime/kernel/memory.py`, `tests/test_kernel_memory.py`,
`experiments/kernel-increment-4/{seed.py,probe_app.py}` and
`scripts/verify-kernel-memory.py`, plus milestone/progress/evidence files.

## Reproduction and evidence

The explicit seed script accepts an evidence directory and uses the existing
binding. It writes memory: do not run it automatically or assume repeating it is
idempotent. The live probe requires a completed retained seed and a fresh output
directory, the existing runtime Python environment and Restate 1.7.9 executable.
It starts/stops only isolated experiment Restate/runtime processes; shared
Qwen/BGE/MIRIX are left running. No hidden chain-of-thought is retained.

[Summary](../../experiments/kernel-increment-4/evidence/resumed/summary.json),
[seed/configuration](../../experiments/kernel-increment-4/evidence/resumed/seed/binding.json),
[actual packets/decisions](../../experiments/kernel-increment-4/evidence/resumed/acceptance/cognition.jsonl),
[raw provider content](../../experiments/kernel-increment-4/evidence/resumed/acceptance/wire.jsonl),
[retrievals](../../experiments/kernel-increment-4/evidence/resumed/acceptance/memory.jsonl),
[verifiers](../../experiments/kernel-increment-4/evidence/resumed/case-verification.json),
[unchanged boundaries](../../experiments/kernel-increment-4/evidence/resumed/unchanged-boundaries.json).

Architecture deviations: none. The user clarified that all eight progression
conditions govern. Exact next increment: 5, bounded HumanDecision child Task;
check its contract fit before implementation and stop on any required unsettled
semantic change. No other roadmap work is implied by this pass.

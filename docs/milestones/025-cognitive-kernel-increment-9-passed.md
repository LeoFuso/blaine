# Increment 9 — bounded derived Project Knowledge

**PASSED.** One optional context provider supplies bounded, source-addressable
navigation from an existing Graphify snapshot. No Cognitive Loop, lifecycle,
contracts, policies, verifier, model adapter or memory behavior changed.

Hypothesis: derived navigation can help identify relevant source while source/Git
and exact artifacts retain authority; stale or absent knowledge must not control
Task execution. The existing Graphify carveout supplied both input and limitations.
No new upstream audit, extraction run, model calls, embeddings or dependency setup.

## Smallest integration

`runtime/kernel/project_knowledge.py` implements the existing ContextProvider callable.
It consumes a bounded Graphify node snapshot plus source-byte digests captured for
that indexed corpus. Each retrieval rechecks the actual selected source bytes.
A HEAD stamp alone is deliberately insufficient. Missing, changed or unversioned
sources are excluded; configured file errors are not silently converted to empty
retrieval. An explicitly absent provider returns no additional context.

Only node identity, label, relative source path/location, exact source digest,
index digest, reported derivation and uncertainty cross into context. The authority
class is always `derived`. Arbitrary summaries, learned answers, confidence claims,
call-graph conclusions and extra authority fields are not forwarded. Digest agreement
means source-version agreement, not proof that Graphify's interpretation is correct.
Consequential claims still require exact source inspection.

Limits: snapshot ≤2 MiB/10,000 nodes; ≤8 candidates checked; ≤3 selected hints;
source verification reads ≤64 KiB per selected file; retrieval respects the existing
4 KiB context-item budget. No generic index service, catalog, watcher or SCIP adapter.

## Retained source and empirical cases

Used the **unchanged initial graph** from the prior pinned carveout, not its later
mutated graph output. Its recorded SHA-256 was rechecked:
`1b08993e20ed568d883aa2b30cb64c1488f6e2d77363616d5b99c8b405696b85`.
Graphify commit `b9cd9570728a5ff3485d2a1e36fe9a1272a368ae`; source corpus commit
`da6654e3a008b7e6be4f7ad54a5c4323bcb8f090`. The selected `runtime/task.py` Git blob
matches current repository source before the controlled stale-fixture mutation.
No current source file was edited for the counterexample.

Three actual isolated Restate Tasks ran through the production Cognitive Loop:

| Case | Retrieval | Authoritative source/result | Outcome |
|---|---|---|---|
| Fresh | Bounded validate_request navigation with exact provenance | Source declaration independently read from exact artifact | COMPLETED |
| Stale | Old navigation excluded after fixture function rename changed source digest | Current `validate_request_current` declaration wins | COMPLETED |
| Absent | No index provider context | Same source inspection and completion behavior | COMPLETED |

Each Task used three **scripted** cognitive turns and three real capability effects:
write the explicitly seeded current-source snapshot → artifact.read → write the
source declaration result. The unchanged CompletionContract verifies exact source
and result digests. The scripted adapter parses supplied source bytes; it has no
hidden tool access. This is not a Qwen or Graphify semantic-quality evaluation.

Totals: 3 durable Tasks, 9 scripted turns, 9 effects, **0 model/embedding calls**.
Maximum retrieved context was **669 bytes**. Exact artifacts, results, completion
references and cognitive/effect Run results were independently checked against the
native journal. Missing knowledge did not require a different loop or lifecycle.

78 focused kernel tests pass: prior 72 plus six boundedness, provenance, freshness,
missing-source and path-scope controls. The Increment 8 production progression is
unchanged. Graphify's broader extraction/update limitations remain documented; this
provider trusts neither graph completeness nor inferred behavioral claims. This
narrow gate does not complete ADR 0014's broader model-quality benchmark.

## Evidence and next gate

- [Summary](../../experiments/kernel-increment-9/evidence/summary.json)
- [Source/provenance/journal checks](../../experiments/kernel-increment-9/evidence/checks.json)
- [Native Task evidence](../../experiments/kernel-increment-9/evidence/acceptance/summary.json)
- [Tests](../../experiments/kernel-increment-9/evidence/focused-tests.txt)
- [Probe](../../experiments/kernel-increment-9/probe.py)

Next gate: Increment 10's sequential context-economy proof on a concrete medium-size
real development/research workload. The roadmap defines topology and measurements,
but does not identify that workload's objective or independent acceptance criteria.
Those were requested while this gate proceeded. No Increment 10 workload has been
invented, submitted or represented as running.

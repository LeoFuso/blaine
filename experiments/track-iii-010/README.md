# Track III.10 — Context propagation across durable boundaries

**2026-09-23 — PASS in the deterministic offline fixture.** All 12 frozen cases meet
expected visibility/provenance/state semantics. **No subsequent increment or production
integration was started.** III.8 remains FAIL and III.8R its separately recorded PASS.

## Hypothesis and boundary

A Task outlives its session, worker and process. Context can survive those boundaries
if the receiver reconstructs effective access from trusted current state. Serializing
fields is not an authority grant. The III.9 UI interruption motivates this question
but is **not evidence** for this experiment; the proof below stands independently.

The [predeclared protocol](PROTOCOL.md), [12 cases](cases.json), [trusted fixture](state.json)
and [security manifest](security.json) were frozen before execution. Corpus SHA-256:
`147f4dc5a520d18e1bb111e97704d841748f5d0ee12296172b2fd93a43c21239`.
[Fixture freeze](evidence/fixture-freeze.json) pins all expectations; [preregistration](evidence/preregistration.json)
pins the evaluator/checker and 401 historical experiment/runtime/milestone files.
The request in [request.json](request.json) is **unsubmitted**: no suitable runtime
creation binding was exposed. No live Restate Task or production durability is claimed.

Only Python standard-library code is used. No model, embeddings, network, database,
MIRIX, Restate integration, remote-machine transport or new persistent service.
Promotion, declassification, verified-outcome admission and production policy semantics
remain unchanged. This increment transports references to already qualified fixture
knowledge; it does not repeat admission or generate new learning.

## Trusted binding versus transfer

[receiver.py](receiver.py) loads harness-owned state independently of caller input.
The receiving route fixes `execution-main` and a trusted participant role. The caller
cannot select the state file, route, participant or mutation mode. Matching a reference
to a known ID alone does not authenticate a caller: **trusted route issuance and file
ownership are assumptions**, not an implemented security transport or process sandbox.

The envelope contains execution/context/binding references, historical policy/topology
references, trace/parent-operation correlation, and deliberately untrusted baggage.
Baggage includes forged readable scopes, domain, authority, provenance, policy snapshot,
ancestor list, prior success receipt and a checkpoint-era memory packet. None grants
access. Unknown or malformed references fail closed; a known foreign context denies.

Each operation reloads the current binding/evidence, validates the entire topology
using the **unchanged III.2 ContextTree**, then applies:

`current lineage ∩ trusted entry domain / current domain grants ∩ current policy`.

The minimal III.10 read adapter represents the previously accepted semantic statuses
explicitly; it is not a production Memory schema or serializer for old opaque tokens.
Historical III.3/III.4 constructors are not silently changed to accept new revisions or
provenance. Whole-tree corruption rejects even in the unreadable employer branch.
Known old revision references are historical annotations, never permission snapshots.

```text
root [public; also holds one explicitly employer-private entry]
├── personal
│   ├── project-old
│   │   ├── task-main -> attempt
│   │   └── task-sibling
│   └── project-new
└── employer-x -> task-x
```

T1 places task-main below project-old. T2 reparents it below project-new while retaining
its personal domain. P1 permits the baseline project entry; P2 excludes `old-rule`.
All content and IDs are synthetic. The root-private record proves that ancestry is
insufficient without independent domain filtering. Global `public-rule` remains visible.

## Execution boundaries and results

Local participants exchange JSON, with a newly constructed receiver/state copy on
every operation. Cognition, worker and verifier do not share privileged binding objects.
Checkpoint writers run as separate OS processes, persist transfer material, then exit.
Only after their exit does the resumed receiver load the checkpoint and current state.
The second-process group uses `subprocess.Popen`/exec with file inputs and JSON stdout.
Child-reported PID/PPID are compared with the parent's actual launched PID privately.

| Case | Expected and actual receiving result | Visible IDs |
| --- | --- | --- |
| A1 valid local cognition → worker → verifier | SUCCESS | failure, observation, old-rule, public-rule, success |
| A2 forged scopes/domain/authority and trace | SUCCESS, no expansion | Same five |
| A3 forged declaration/success provenance | SUCCESS, no upgrade | Same five, trusted statuses |
| A4 known foreign context | DENIED | None |
| B1 valid checkpoint/resume | SUCCESS | Same five |
| B2 P1 checkpoint, current P2 | SUCCESS, narrowed | failure, observation, public-rule, success |
| B3 T1 checkpoint, current T2 | SUCCESS, reparented | failure, new-rule, observation, public-rule, success |
| B4 incomplete checkpoint reference | INVALID_CONTEXT | None |
| C1 valid second-process transfer | SUCCESS | Baseline five |
| C2 forged scopes in receiving process | SUCCESS, no expansion | Baseline five |
| C3 serialized P1, receiving P2 | SUCCESS, narrowed | Same four as B2 |
| C4 previously successful transfer, current evidence missing | UNAVAILABLE | None |

**12/12 primary cases, four per group; 1,460 independent checks PASS.** There are
29 supplemental probes and **60 complete output exports** scanned. The primary run
executes **26 real subprocess operations**, including checkpoint writers, receivers,
same-state replays and selected supplemental probes. No network transport is involved.
Normal subprocess exits are 0 with empty stderr; failure states are machine responses,
not crashes. PRIVATE binding evidence and raw success/failure logs never enter stdout.

## Continuous access, provenance and replay

Every successful receiver reads Memory again. B2's checkpoint contains the previously
permitted old-rule, yet the P2 response cannot recover it from that historical packet.
B3 does not honor the old ancestor list. C4's prior successful response is retained,
but removal of current binding-evidence yields UNAVAILABLE on both subsequent reads.
Identical immutable trusted state produces identical responses on every case replay.

USER_DECLARATION/DECLARED, AGENT_OBSERVATION/UNVERIFIED and
VERIFIED_OUTCOME/VERIFIED_SUCCESS or VERIFIED_FAILURE survive all valid boundaries.
Serialized claims cannot turn failure into success or an observation into a declaration.
Human declaration remains distinct from learning and promotion; verified knowledge
remains personal-domain scoped. The prior qualification is a historical fixture fact,
not evidence that the underlying work would satisfy a changed Completion Contract.

A supplemental worker writes `task-main::note-1` through the closed ordinary-write
operation; the later verifier in a separate process re-queries and sees it. Parent
project-old cannot see it, while an independently trusted attempt binding can. The
write ID is context-scoped and provenance is runtime-assigned. Attempts to name a
parent, destination or provenance in the write request deny. No promotion is invoked.

Bounded trace and parent-operation correlation values propagate. Changing trace-main
to trace-forged leaves exact visibility unchanged. Correlation is not identity, a
credential or evidence. No global cache/index/revision counter is exposed. Process
attestations and harness operation numbers are experimental audit metadata, not Memory
freshness or authorization fields.

## Budgets, diagnostics and leakage

Responses distinguish SUCCESS, EMPTY, DENIED, UNAVAILABLE and INVALID_CONTEXT.
Denied/invalid/unavailable receipts are null and diagnostics contain only the result
state. Known protected IDs and nonexistent IDs produce identical denial responses.
Unknown policy/topology references, hidden missing-parent/cycle/self-parent/duplicate
nodes, malformed JSON/duplicate keys and contradictory bindings all fail closed.
Unavailable current policy never falls back to the envelope's old snapshot.

Every complete serialized response includes content, provenance, receipt, diagnostic,
partial flag and stdout newline in the **2048-byte** bound. Primary maximum is **1051
bytes**; maximum including the saturation probe is **1696 bytes**. That probe includes
one of eight additional eligible multibyte entries and marks the rest omitted. An
exact-size edge additionally proves marker accounting when a would-be untruncated
response is one byte too large. Stable ID ordering and whole-entry selection are
experimental choices, not relevance ranking. No cache was introduced.

Independent scans cover full stdout/stderr, responses, receipts and serialized export
metadata: **zero forbidden content, zero forbidden metadata**. Permission is evaluated
per receiving scope/state; P1's legitimately visible historical output is not judged
under later P2. Public exports are separate from protected administrative records
containing envelopes, policy snapshots, source entries and raw audit canaries. No
production telemetry export system is implemented.

## Controls, corrections and reproducibility

| Isolated mutation | Actual violation | Independent checker |
| --- | --- | --- |
| Trust serialized readable scopes | A2/C2 disclose protected root/foreign/sibling/descendant records | Exit 1; 6 failed checks; 16 content and 24 metadata hits across replayed exports |
| Trust serialized P1 snapshot | B2/C3 disclose old-rule after P2 excludes it | Exit 1; 8 failed checks; 4 content and 4 metadata hits |
| Trust serialized provenance | A3 renders failure as VERIFIED_SUCCESS and observation as USER_DECLARATION | Exit 1; 4 failed checks |

These are real returned violations, not test crashes. Mutations are explicit harness
flags; default execution never uses them. [Aggregate verification](evidence/summary.json)
independently inspects mutant records and launches the same checker expecting exit 1.

[Initial verification](evidence/initial-verification.json) is retained: its only failure
was a scanner false positive matching the already-permitted ID `observation` inside
new observation text. The scanner was corrected to distinguish scope-permitted entries
from entries merely absent in a write receipt. Static review also corrected the JSON
`false`/`true` length edge and made trusted participant roles explicit in child-process
invocation. [Preregistration corrections](evidence/preregistration.json) record source
hashes and reasons. Frozen primary cases, expectations and thresholds never changed.

After those implementation corrections all controls were rerun, then two fresh default
runs with hash seeds 7 and 83 reproduced [results](evidence/primary/results.json) and
[exports](evidence/primary/exports.json) **byte-for-byte**, with all checks passing.
Actual PID/PPID attestations necessarily vary; they are separately verified and not
normalized into fabricated deterministic process identities.

```bash
# Read-only verification of retained primary and mutation evidence:
python3 experiments/track-iii-010/verify.py
# Fresh deterministic execution into a temporary output directory:
python3 experiments/track-iii-010/run.py --output /tmp/iii10-reproduction
python3 experiments/track-iii-010/check.py /tmp/iii10-reproduction
# Deliberately unsafe control; checker must exit 1:
python3 experiments/track-iii-010/run.py --mutation stale-policy --output /tmp/iii10-mutant
python3 experiments/track-iii-010/check.py /tmp/iii10-mutant
```

Other retained evidence: [primary verification](evidence/verification.json),
[process attestations](evidence/primary/process-attestations.json),
[mutation controls](evidence/mutation-controls.json), [reproduction](evidence/reproducibility.json),
[documentation checks](evidence/documentation-checks.json).

## Architecture implications, limits and post-Track-III recommendation

The accepted Context/Memory semantics survive this finite serialization/checkpoint/
process experiment. Persist references and historical evidence; reconstruct current
authority at each operation. A prior response is not a durable grant, and a trace is
not a capability. The existing hierarchy/security/provenance concepts require no
weakening; this minimal experimental reference/registry adapter is not a production
contract. III.8 FAIL and III.8R PASS retain their original scope and evidence.

The harness assumes an **atomic, trusted, immutable state snapshot per operation**.
It does not resolve races between validation and side effects, crash-consistent writes,
authorization issuance, multi-machine identity, revocation dissemination/latency,
distributed policy storage, retention, durable idempotency, malicious code with file
access or cryptographic attestation. Known historical revision lists are tiny fixture
catalogs, not a historical-policy service. Persisting a file and restarting a process
is not proof of Restate durability or production recovery. Hashes detect byte changes;
they are not signatures or protection against a malicious evidence author.

Recommended next work, **not started or authorized by this increment**: consolidate
Track III findings into a reviewable architecture decision and contract gap analysis.
Specify ownership of ExecutionContextRef issuance/resolution, current policy/topology
snapshots and their freshness/atomicity, scoped diagnostics, evidence references and
per-operation revalidation. Map these to existing PolicyGate, Restate and capability
boundaries without changing their ownership. Include explicit residual risks and a
separately proposed minimal integration slice with acceptance tests; obtain human
architectural approval before implementing that slice. Remote identity/transport and
concurrency remain separate work. Do not infer a hard NoveltyGate from advisory PASS.

No human architectural decision is required to close III.10: no conflict was found.
Choosing production contracts, authority issuer and integration priority does require
a future human architectural decision. No subsequent implementation began; no push.

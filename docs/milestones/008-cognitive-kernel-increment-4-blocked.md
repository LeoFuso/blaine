# Increment 4 — MIRIX context: BLOCKED / live acceptance UNVERIFIED

Historical stop, now resolved. User supplied the existing client/user IDs and
clarified conditional progression. See [Increment 4 PASS](009-cognitive-kernel-increment-4-passed.md).

Hypothesis: a bounded MIRIX embedding retrieval can inform Qwen through the
existing ContextProvider seam, while Task state, exact evidence, policy and
completion remain authoritative. Increment 3 remains CLOSED/PASSED.

## Implemented, not live-validated

`runtime/kernel/memory.py` adds one optional callable provider. It requests only
semantic memory through `GET /memory/search`, with embedding search, two results,
a 512-character query, a 32 KiB transport limit and at most 4096 bytes of selected
context. Items carry the MIRIX ID/source, a digest of the retrieved representation,
`authority=derived`, semantic-memory classification and explicit uncertainty.
The digest identifies retrieved bytes; it does not make memory authoritative or
establish when its claim was true. Empty successful retrieval supplies no items.
Explicit API errors fail retrieval rather than inventing memory. There is no
ingestion code, cache, background work or lifecycle integration.

All 27 focused unittest cases pass, including six synthetic provider checks.
The tests cover provenance, bounds, empty results, malformed/error responses,
conflicting authority claims and local-only endpoint selection. These are
deterministic application tests, **not live MIRIX/BGE/Qwen acceptance**.
All 11 previously recorded Increment 3 source digests remain unchanged, including
kernel, contracts, context reconstruction, JSON-only adapter and original probes.

## STOP record

- **EXPECTED:** attach to the already validated MIRIX client/agent hierarchy,
  verify its local Qwen/BGE configuration, explicitly seed experiment memory,
  then execute fresh-process recall, absence and conflict Tasks.
- **OBSERVED:** Qwen and BGE model-discovery endpoints return HTTP 200 and report
  `Qwen/Qwen3.5-9B` and `BAAI/bge-m3`, owned by `vllm`. MIRIX OpenAPI is reachable.
  `GET /agents?limit=10` with the documented default client/org returns HTTP 200
  and `[]`. The retained live-validation narrative does not identify the actual
  previously validated client. That client's existence/configuration has not
  been disproved; its binding is missing from available evidence.
- **IMPACT:** no architecture change. Live acceptance cannot establish MIRIX
  model/embedding provenance or retrieve a seeded fixture yet. No Qwen inference,
  embedding generation, MIRIX writes or runtime probe Tasks were executed in this
  increment. A/B/C are all **NOT RUN / UNVERIFIED**, not failed semantic tests.
- **SMALLEST NEXT DECISION REQUIRED:** provide the non-secret existing MIRIX
  client ID and, if applicable, user ID used by the validated setup. No keys are
  requested. Resume by reading that client's persisted agent configuration;
  do not create a replacement hierarchy or alter service configuration.

The existing MIRIX API requires a client binding; this is an integration-input
blocker, not evidence that MIRIX is unavailable or architecturally incompatible.
User clarification was requested. Work stops here rather than guessing client
identities, accessing unrelated memories or changing the validated configuration.

Evidence: [summary](../../experiments/kernel-increment-4/evidence/summary.json),
[HTTP discovery](../../experiments/kernel-increment-4/evidence/availability.json),
[tests](../../experiments/kernel-increment-4/evidence/tests.json),
[test names/output](../../experiments/kernel-increment-4/evidence/tests.txt),
[unchanged boundaries](../../experiments/kernel-increment-4/evidence/unchanged-boundaries.json).

Exact next work: finish **Increment 4 only**, beginning with the missing binding.
No later increment is started. The current request includes conflicting stop
after 4 / conditional advancement wording; clarification remains pending and
does not affect this blocked gate.

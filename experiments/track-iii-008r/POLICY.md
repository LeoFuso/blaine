# III.8R predeclared selection policy

Frozen before recovery comparisons; implementation parameters are in [policy.json](policy.json).
Original III.8 remains FAIL. The asset manifest pins every original experiment file,
including both snapshots, query/oracle/security manifests, vectors, graph indexes,
raw candidate lists and lexical baseline outputs. No new retrieval or inference runs.

1. Validate each mechanism contribution independently against trusted scope, current
   source, visible revision and AST relations. Remove invalid contributions before
   ranks, fusion or packet competition. A valid lexical contribution is independent
   of any stale semantic/structural contribution to the same target.
2. Deduplicate by revision/path/symbol/declaration line. Multiple mechanisms become
   provenance on one authoritative target, not repeated source payloads.
3. Compress repeated source-text families in each valid mechanism ranking: replace
   decimal digit runs in declaration text with `#`, hash that text, and assign rank
   on the first appearance of a family. This query-independent rule addresses cloned
   diagnostic declarations. It does not establish semantic equivalence, discard a
   source target, or assert that differing constants have equal behavior.
4. Fuse ranks with exact rational reciprocal-rank fusion, **k=60**. No arithmetic
   combines raw BM25, cosine and graph scores. Preserve exact whole-symbol matches
   first, explicit structural answers next, then descending fused rank. Ties use
   best family rank and target identity. No oracle/category/identifier exceptions.
5. Traverse fused targets in diversity rounds: one per source-text family before
   second representatives. Exact matches remain mandatory first. Attempt whole-entry
   selection greedily within **2048 serialized UTF-8 bytes**, testing the complete
   response with both final partial states. Oversized candidates consume no capacity.
6. Use one scoped source-manifest revision for the packet, compact L/S/G discovery
   provenance, authoritative path/symbol/line and the first **80 source characters**.
   Structural edges reference selected entry indices. Diagnostics, relations, status
   and truncation metadata all count toward the budget. Per-entry hashes are redundant
   with the immutable snapshot identity; retained internal evidence keeps them.

Why these choices: RRF avoids cross-mechanism score calibration; family compression
limits cloned text monopolies; exact confidence is lexical equality; shared revision
and compact edges reduce duplicated metadata. These are generic selection rules
motivated by III.8 diagnostics, not unseen-corpus validation. Digit normalization can
conflate materially different constant-bearing implementations and needs broader
research. A PASS here would not authorize production clone suppression.

The original threshold is unchanged: at least two unique new required non-lexical
hits per revision; zero lost exact hits, stale or forbidden output; canonical reuse
included and all mandatory combined targets retained. Structural incremental utility
remains unproven if its additional target count stays zero.

Controls: bypass freshness with retained A-derived data for B; bypass isolation with
retained global candidate lists; and restore late merged-target invalidation so stale
contributions suppress fresh lexical hits. Each must cause an actual independently
observed defect and a nonzero checker exit. Correct behavior is the default and is
reproduced after controls. One policy only; no ranking adjustment after outcomes.

# Track III.1 source-research evidence

Research acceptance: **PASS**, 2026-09-23. This is a documentation/source-review
increment, not a runtime or retrieval benchmark. See the
[research report](../../docs/research/track-iii/001-reference-systems.md) and
[milestone](../../docs/milestones/042-track-iii-1-reference-systems.md).

- [TaskSpec draft](request.json): **unsubmitted**; no suitable creation binding
  was exposed. No runtime Task identity/state is claimed.
- [Source manifest](evidence/source-manifest.json): seven upstream commit pins,
  inspected-source inventory, file SHA-256 values and primary-source links.
- [Review record](evidence/review.json): bounded research hypotheses, acceptance
  reasoning, limitations and mechanical documentation checks.

Sources were fetched read-only into disposable checkouts under
`/tmp/blaine-track-iii-sources/`. No upstream installer, hook, test runner or model
was invoked. Those checkouts are not retained deliverables or dependencies.
To reproduce a source observation, fetch its recorded upstream commit and inspect
the linked file/function; verify file bytes against the manifest if needed.

The report distinguishes current source, documentation, historical Blaine
experiments, upstream benchmark claims and architectural inference. Historical
live MIRIX/Graphify evidence was read, not rerun. No production security or
performance result is inferred from documentation checks.

**III.2 remains unstarted.** Its fixture tree, negative cases and expected evidence
are specified in the report. This directory contains no III.2 implementation.

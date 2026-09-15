# TaskSpec examples

These examples intentionally show optional fields when they are useful. They are not a form the user must fill out; the Personal Agent should produce the smallest TaskSpec that preserves intent, constraints, and verifiable completion.

These public examples are complete structural drafts, not submitted Tasks or a
closed taxonomy. User-authorized scope is illustrated explicitly. References are
relative to the relevant Task workspace or an authorized source collection.

## Investigation

```yaml
objective: Identify why the fixture import fails without changing files.
mode: interactive
context:
  - need: Failing input and observed error
    source: fixtures/import-failure/
    freshness: current fixture revision
    sharing: local-only
capabilities: [read task workspace, run read-only diagnostics]
autonomy:
  allowed: [inspect fixture and run read-only diagnostics]
  ask_before: []
  forbidden: [modify files, access production]
cloud:
  policy: forbid
completion:
  - criterion: Explain the failure cause or narrow the remaining hypotheses.
    evidence: Reproduction output and source references supporting each conclusion.
```

## Coding

```yaml
objective: Fix empty-input handling in the sample parser and show the diff.
mode: interactive
context:
  - need: Parser implementation and tests
    source: sample-parser/
    freshness: current task workspace revision
    sharing: local-only
capabilities: [read task workspace, edit task workspace, run tests]
autonomy:
  allowed: [modify parser and regression tests in task workspace, run tests]
  ask_before: [commit, push]
  forbidden: [change unrelated behavior]
cloud:
  policy: ask
completion:
  - criterion: Empty input follows the documented parser contract.
    evidence: Regression test outcome and relevant existing test results.
  - criterion: Changes are reviewable and limited to the requested fix.
    evidence: Final diff with workspace revision and scope inspection.
```

## Research and summary

Summarizing a paragraph already supplied in chat can be direct. Gathering and
comparing source material for a retained report is durable work.

```yaml
objective: Compare three public file formats for archiving tabular measurements.
mode: interactive
context:
  - need: Official CSV, JSON, and Parquet format documentation
    freshness: current published documentation at execution time
    sharing: cloud-allowed
capabilities: [read public web, write report artifact]
autonomy:
  allowed: [read public documentation, write comparison report]
  ask_before: []
  forbidden: [upload user datasets]
cloud:
  policy: allow-within-budget
  max_usd: 2
completion:
  - criterion: Compare type fidelity, readability, and storage tradeoffs for all three formats.
    evidence: Retained report with source URLs, retrieval dates, and explicit uncertainties.
```

## Bounded watch / scheduled work

This illustrates a user request with explicit interval, end time, and local output.
A one-shot scheduled task uses `at` instead of the recurring fields.

```yaml
objective: Watch a public release feed for a new stable release during the next day.
mode: background
context:
  - need: User-selected public release feed and baseline version
    source: inputs/release-feed.yaml
    freshness: fetch current feed on each scheduled observation
    sharing: local-only
capabilities: [read selected public feed, write report artifact]
autonomy:
  allowed: [poll selected feed, retain observation report]
  ask_before: [send external notification]
  forbidden: [install release]
cloud:
  policy: forbid
completion:
  - criterion: Stop on the first new stable release or at the observation window's end.
    evidence: Timestamped feed observations and detected version or no-match report; disclose observation gaps.
schedule:
  every: 30m
  starts_at: '2026-09-15T09:00:00-03:00'
  ends_at: '2026-09-16T09:00:00-03:00'
```

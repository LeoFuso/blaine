# Triaging & Routing Policy

Every substantial task begins with a compact triage before work starts. This policy provides the detailed classification matrix and thresholds referenced in BLAINE.md's core triage framework.

## Classification Matrix

For every non-trivial task, classify on six dimensions:

| Dimension | Values | Notes |
|-----------|--------|-------|
| **Size** | small / medium / large | See size thresholds below |
| **Risk** | low / medium / high | Based on blast radius and reversibility |
| **Work type** | deterministic / latent / hybrid | Determine whether the answer can be verified by computation before invoking reasoning |
| **Execution** | local solo / fan-out (named agents) / delegation (external specialist) | Default to local solo; fan out or delegate when justified |
| **Verification** | targeted checks / independent critic / full relevant suite | Maps to size — see thresholds below |
| **Frontier budget** | none / one prepared call / multiple calls by independent work | Justify each frontier token against the purpose statement |

## Size Thresholds and Decision Criteria

### Small tasks

- Scope: single-file or two-file mechanical edit with no behavior change
- Execution: local solo. No fan-out by default.
- Verification: run only checks covering what was touched — target coverage, not ritual
- Escalation: when evidence shows the task is broader than initially triaged, re-triage up immediately and report the updated classification

### Medium tasks

- Scope: localized behavior change or bug fix inside one service/module; investigation with real judgment required
- Execution: local solo by default. Fan out only if independent units exist (see [orchestration.md](./orchestration.md)). Delegate when frontier capability materially improves the result, per [local-first-and-context.md](./local-first-and-context.md).
- Verification: enough tests to cover the blast radius. Contract changes require contract-level verification.
- Escalation: if work touches multiple modules or reveals unexpected architectural coupling, re-triage up immediately

### Large tasks

- Scope: cross-service changes, architecture decisions, new features, any judgment-heavy design
- Execution: Full protocol — decomposition into bounded work units, builder-critic separation (see [orchestration.md](./orchestration.md)), full test suite for every touched unit. **Fan-out to parallel builders only when useful independent sub-units exist**; tightly coupled large tasks may use a single builder.
- Verification: independent critic + full relevant suites for all affected contracts
- Escalation: default escalation for any change that exceeds the capacity of a single-agent workflow

### When uncertain between sizes

Start smaller and escalate when evidence shows the task is broader. Escalation is cheaper than unnecessary orchestration but more important than staying wrong about scope. Print an updated triage line in context when reassessing.

## Four-Line Triage Block

When surfacing the triage helps the human follow the work, use this compact format:

```
Size: small | medium | large — why
Execution: local solo | fan-out (who, on what) | delegation (why)
Verification: which checks, and how much of the suite — why
Branch: <name> — or NONE for trivial/no-write work
```

## Cross-references

| Resource | Location |
|----------|----------|
| Core triage framework & decision rules (compact) | [BLAINE.md](../../BLAINE.md) |
| Keep-vs-delegate criteria | [local-first-and-context.md](./local-first-and-context.md) |
| Fan-out decision tree, reader/writer isolation, builder-critic | [orchestration.md](./orchestration.md) |
| Completion states, verification-pass levels, safety gates | [task-completion-and-lifecycle.md](./task-completion-and-lifecycle.md) |

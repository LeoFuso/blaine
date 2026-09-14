# Orchestration Policy

Fan-out decisions, multi-agent isolation rules, and builder-critic separation for coordinated task work in Blaine. This file governs the *how* of multi-agent execution — **[triage-routing.md](triage-routing.md)** for classifying task size and choosing an execution category (local solo vs fan-out vs delegation).

## Why this exists

Without these rules, local agents default to over-parallelism or under-isolation. Both are wastes: too many concurrent writers corrupt state; unneeded parallelism burns tokens that should fund one good call instead of three mediocre ones. This is the minimum machinery for safe coordination.

## Fan-out decision criteria

Fan out only when two conditions hold simultaneously: **multiple genuinely independent sub-units exist** AND **one agent could not reason about them jointly** (not just execute, but understand what connects the units). Otherwise stay local — one good call beats three mediocre ones.

Use multi-agent fan-out when:
- Work decomposes cleanly into independent units that would reduce wall-clock time materially through parallelism.
- Each unit requires a different specialist tool or capability no single agent can provide right now.
- Independent perspectives would raise confidence on a judgment-heavy deliverable (e.g., competing architecture options).

Fan out is a capability, not a ritual. For trivially parallel work where coordination overhead exceeds the parallelism gain, do it serially. The triage line (`Execution: fan-out (who, on what)`) is sufficient justification — no additional boilerplate is required.

### Fan-out scope limits

Size thresholds that determine *when* to escalate toward fan-out live **[triage-routing.md](triage-routing.md)**. Cross-reference them here rather than duplicating. The routing decision is: Small→local solo; Medium→solo by default, fan out only if independent units exist and one can't reason jointly; Large→decomposition with parallel builders and full builder-critic separation per below.

## Reader/writer isolation rules

- **Readers** (analysis, grep, inspection) may share a workspace and run in parallel freely — reading never corrupts state.
- **Writers must never edit the same file.** Partition strictly by directory or concern path to prevent silent collision.
- When concurrent writers operate on the same repository, isolate them with separate worktrees/branches or equivalent (task-specific isolation is acceptable if blast radius is narrow and bounded).
- One task branch per independent implementation effort when only one writer is active — do not manufacture worktrees for ceremony on small work.

## Variant tournaments

Use variant tournaments when evaluating competing designs, UX approaches, or architecture decisions where multiple valid answers exist and the quality of the final choice matters. Run independent evaluations from each variant; synthesize a single recommendation rather than presenting options without guidance.

Variant tournaments are useful for judgment-heavy units (design, UX, architecture). They are **not required** for routine fixes, boilerplate changes, or deterministic decisions where one correct answer exists. Drop heavy procedural detail (blind labelling, artifact path conventions) unless the work genuinely needs that rigor — Blaine moved away from harsh-by-default rituals for good reason.

## Builder-critic separation

Use builder-critic separation for medium and large work where quality matters and the cost of error is non-trivial:
- Code changes with blast radius beyond a single file or module.
- Documentation updates affecting team-facing material, contracts, or procedures.
- Architecture decisions that lock in implementation paths.

For these cases the builder writes the deliverable and an independent critic validates against the acceptance criteria or reference rubric. The builder must **not** be the sole authority certifying their own work — even for medium-size changes. For small work (single-file mechanical edit, no behavior change) one fresh verification pass is sufficient.

### How a critic should work

1. Receive the deliverable and its acceptance criteria or reference rubric as a single packet.
2. Evaluate independently: identify concrete gaps rather than giving confidence statements.
3. Report findings with named criteria — vague "it could be better" is not actionable.
4. If remaining gaps are within scope of the builder, return the artifact for revision against those specific named criteria.

The critic should **not** receive the builder's justification or solution path — bias comes from giving them a biased starting premise (desired verdict or inlined solution steps), not from feeding them the answer and asking for confirmation.

### Quality-loop convergence

Quality loops must converge. If repeated review/revision rounds do not improve the same named criteria, stop and surface what is blocking progress rather than lowering the bar silently. **Report as BLOCKED** when improvement stalls on clearly defined criteria that remain unmet. See **[Final Verification & Communication](../../BLAINE.md#final-verification--communication)** for completion-state definitions including when to escalate a stall.

## Delegation packet hygiene

When sending context to any worker (builder, critic, or specialist): send the minimum sufficient context, not a repository dump and not incomplete fragments. Use the standard packet format from **[BLAINE.md → Delegation-packet template](../../BLAINE.md#delegation-packet-template)**. Never include secrets in delegation packets.

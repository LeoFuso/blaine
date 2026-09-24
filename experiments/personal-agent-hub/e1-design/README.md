# Completion Contract and E1 design slice

**Status: DESIGN — no runtime, client, transport or deployment change.**
Branch `design/completion-contract-e1`, 2026-09-23; reconciled 2026-09-24. Ran in parallel with E0.D
implementation in another worktree; no E0.D files or uncommitted work were used.

## Outputs

- [Completion Contract v1](../../../docs/contracts/completion-contract.md) and
  [ADR 0026](../../../docs/decisions/0026-completion-contract-is-a-durable-task-primitive.md).
- [E1 workspace capability](../../../docs/contracts/workspace-capability.md) and
  [ADR 0027](../../../docs/decisions/0027-ide-delegation-is-workspace-authority.md).
- [Contract/journal fixtures](contract-examples.json) — synthetic, not runtime-validated.
- Revisions to the [Hub design](../../../docs/personal-agent-hub.md), roadmap and indexes.
- [Unsubmitted TaskSpec draft](request.json) for this design work: no development
  Task-creation binding was available; no runtime Task ID or state is claimed.

## Operator decisions recorded (2026-09-23)

1. Connecting Blaine to IntelliJ with **Pass IntelliJ MCP server** (`use_idea_mcp`)
   enabled is the operator's delegation of the IntelliJ-exposed project capability
   surface. No second workspace-approval system in Blaine.
2. ACP `configOptions` are an input channel for operator constraints (e.g. Read
   Only), compiled into effective authority. PolicyGate is the single enforcer.
3. Keep delegated scope, Task relevance, user constraints and effective authority
   separate. The local client is a protocol/capability bridge, not a second
   PolicyGate; it does not project the MCP tool set.
4. Do not fall back to a Blaine-owned filesystem provider for theoretical sandboxing.
5. E1 must prove that a READ_ONLY Task invokes no mutating capability although the
   delegated surface contains them, using the capability journal as evidence.

Follow-up decisions (2026-09-24):

6. The Hub is in the trusted computing base of the personal deployment. The
   compromised-Hub residual is accepted; no local authorization engine is added.
7. `blaine connect` does not mutate JetBrains configuration. `blaine integration
   jetbrains install` (invoked by the installers) registers Blaine and sets its
   per-agent `use_idea_mcp = true`; `check`/`doctor` verify it.
8. Designated, structured trusted project policy may create REQUIRED criteria;
   ordinary repository evidence, Memory and model inference stay advisory, per
   Context Plane source provenance.

## Reconciliation (2026-09-24)

The design was first written on local `main` at `2327187`. `origin/main` had since
gained the Track III Context Plane (`6a0618d`) while local `main` gained accepted
E0.D (`6608e17`, unpushed). A literal rebase onto `origin/main` would have rewritten
the shared E0.C line (including commits behind published alpha tags), so the branch
was rebuilt as: local `main` → merge of `origin/main` (clean) → replayed design →
corrections. ADR 0025 had become the Context Plane ADR, so the design ADRs are 0026
and 0027. The pre-reconciliation commit is kept as local branch
`backup/design-e1-dca1d77`.

## Upstream observations (not live IDE evidence)

JetBrains documentation and `intellij-community` source (`plugins/mcp-server`)
were read on 2026-09-23: per-agent `use_idea_mcp` (default false); per-call project
resolution (`projectPath` argument, headers, roots) across open projects;
`read_file` accepts absolute paths/VFS URLs but refuses files outside project,
library and SDK roots and returns the IDE document; search tools use project scope;
`list_directory_tree` checks the project directory lexically; mutating and executing
tools share the server; an isolated authorized session uses a per-session token.
The installed IDE's actual `session/new` payload was not observed; that is the
first E1.A gate.

## Local checks

Recorded in the final commit message and the design review: JSON parse of the
fixtures and draft, local Markdown link/anchor resolution for changed documents,
and `git diff --check`. No tests, live IDE, Tailscale, Hub or Restate were run.

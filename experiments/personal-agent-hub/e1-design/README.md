# Completion Contract and E1 design slice

**Status: DESIGN — no runtime, client, transport or deployment change.**
Branch `design/completion-contract-e1`, 2026-09-23. Ran in parallel with E0.D
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

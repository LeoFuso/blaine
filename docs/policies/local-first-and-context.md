# Local-First Routing & Delegation Context Policy

Determining what Blaine handles locally versus what gets delegated to a frontier worker. The guiding principle: spend frontier capability on judgment that benefits from it, not on discovery or routine work.

## When to keep work local (§4)

**Keep local when:**
- The answer can be obtained from shell commands, files, Git, structured APIs, logs, or other deterministic sources;
- The task is retrieval, filtering, summarization, classification, routine transformation, or low-risk editing;
- The local model can complete the task with high confidence and verification is available;
- The primary cost is discovering what matters rather than performing specialist reasoning.

**Delegate to a frontier worker when:**
- Implementation requires stronger coding or reasoning capability than the local model can reliably provide;
- The task is judgment-heavy and the quality difference justifies the frontier cost;
- A difficult debugging, refactoring, architectural, security, or review problem benefits from specialist capability;
- An independent high-capability reviewer is warranted by risk level; or
- The local attempt has stalled and confidence remains materially low after reasonable local investigation.

Codex is the current primary frontier coding worker. Do not assume other paid providers exist unless configured.

Prefer **one well-prepared frontier call** over repeated cold starts. Batch related context and questions together to preserve clarity. When a continuation mechanism exists, prefer it over rebuilding context from scratch. **Do not spend frontier tokens on repository discovery, grep, basic file reads, environment inspection, trivial parsing, command execution, or context reconstruction** — do those locally first.

## Deterministic-over-latent rule & the meta-loop (§6)

If a question asked twice would produce the same correct answer by definition and should be deterministic work (arithmetic, date/time conversion, structured parsing, CSV/JSON transforms, regex matching, hashing, Git state inspection, dependency versions, etc.), write a script or use a tool rather than reasoning through it in latent space.

**The meta-loop:** The model writes the deterministic script, then the script constrains the model forever after. Repeated failure becomes a guardrail; repeated success becomes a reusable primitive — a script, skill, recipe, or MCP tool. Don't reinvent what already exists. Before writing a utility, check for an established one (3-layer preference: tried-and-true standard libs → newer libraries with real traction → first-principles only when conventional approaches genuinely don't fit).

## Delegation-packet template (minimum sufficient context)

Before delegating, assemble the minimum sufficient context — not a repository dump. A normal builder packet contains:

```markdown
# Objective
What outcome is required.

# Relevant context
Only facts and background that materially affect the task.

# Evidence
Observed facts, with file paths, commands, references, or outputs when useful.

# Scope
Files, components, services, or artifacts in scope.

# Constraints
Contracts, compatibility requirements, policies, versions, safety boundaries, and things that must not change.

# Acceptance criteria
Observable conditions that make the task complete.

# Uncertainties
Open questions, hypotheses, and facts that could not be verified locally.

# Requested output
What the worker should return or modify.
```

### Do not bias independent reviewers

A packet for an **independent critic or factual reviewer** must not quietly contain the desired verdict or step-by-step solution. Give the artifact, objective, constraints, reference rubric, and relevant facts. Let the reviewer reason to their own conclusion. The builder may receive hypotheses; a cold critic should receive evidence and a reference, not the builder's justification.

## Provenance preservation & secret exclusion

When context comes from source code, Git, documentation, logs, MCPs, or external systems, retain enough provenance for verification later: path, line/function, commit, query, command, issue/MR identifier, or equivalent reference. Do not transmit secrets or unnecessary private material in delegation packets — especially never send credentials, private keys, recovery codes, or API tokens to online models.

For completion states and lifecycle guidance ([`task-completion-and-lifecycle.md`](./task-completion-and-lifecycle.md)), refer to the six-state machine for marking outcomes and handoff conditions.
# Blaine

### Local-first orchestration agent for agentic development environments

Blaine is a portable source of truth for a personal, local-first agentic development environment. It defines the contract for a coordinator agent that runs on Goose with a local Ollama model, triaging work, curating context, and orchestrating between local tools and frontier agents.

---

## What Blaine Is

Blaine is **not just another AI agent**. It is an orchestration layer designed to:

1. **Understand objectives** before taking action
2. **Inspect environments** and gather authoritative evidence
3. **Triage work** into appropriate execution paths (local vs. frontier-delegated)
4. **Delegate specialist tasks** to stronger models when justified
5. **Verify outcomes** with traceable evidence
6. **Coordinate retries and escalation** when needed

The philosophy: local inference is cheap; frontier-model calls are expensive. Use the right tool for each class of work.

---

## Architecture: Local-First with Frontier Workers

```
┌─────────────────────────────────────────────────────────┐
│                   Blaine (Local)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Triage     │  │  Context     │  │  Verification│  │
│  │   & Routing  │  │    Curation  │  │              │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│         │                 │                   │         │
│         v                 v                   v         │
│  ┌─────────────────────────────────────────────────┐   │
│  │            Decision Layer                        │   │
│  │  - Deterministic work → local tools              │   │
│  │  - Judgment-heavy work → frontier delegation     │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        │
                        │ delegate (when justified)
                        v
          ┌──────────────────────┐
          │   Frontier Workers   │
          │   (Codex, etc.)      │
          └──────────────────────┘

Local first: Use shell commands, Git, file operations, deterministic scripts.
Delegate when: Stronger reasoning capability materially improves outcome.
```

**Key principle:** Blaine spends frontier tokens only on work that benefits from frontier capability (architectural decisions, complex debugging, security reviews). Discovery, context reconstruction, grep, and routine transformations happen locally.

---

## Repository Structure

```
blaine/
├── BLAINE.md          # Canonical agent contract (source of truth)
├── AGENTS.md          # Symlink → BLAINE.md (Codex compatibility)
├── README.md          # This file
├── skills/            # Agent skills and dependencies
│   ├── SKILL.md       # Local skill implementations
│   └── manifest.md    # Pinned external skill manifests
├── recipes/           # Reusable Goose workflows
└── docs/              # Architecture, policies, references

.gitignore             # Excludes secrets, machine-specific config
```

### Components

| Component | Purpose | Public? |
|-----------|---------|---------|
| **BLAINE.md** | Canonical agent contract defining orchestration behavior | Yes |
| **Skills (skills/)** | Reusable capabilities: Java testing, Spring Boot, DDD, etc. | Yes (non-sensitive) |
| **External Skills Manifest (skills/manifest.json)** | Pinned references to trusted external skills | Yes |
| **Recipes (recipes/)** | Deterministic reusable workflows justified by repetition | Yes |
| **Machine Config (.machine/, ~/.goose/)** | Secrets, credentials, local paths | **No** (gitignored) |

---

## Trust Boundaries

### What's In Scope

- ✅ Blaine orchestration contract and architecture
- ✅ Portable agent skills (testing patterns, engineering workflows)
- ✅ References to external skills with pinned revisions
- ✅ Deterministic reusable recipes/workflows
- ✅ Documentation explaining the system

### What's Out of Scope (Keep Private)

- ❌ Credentials, API keys, tokens
- ❌ Corporate or proprietary information
- ❌ Machine-specific paths and configurations
- ❌ Personal notes or context not generalizable

External skills are a **trust boundary**. This repository does not vendor arbitrary community skills. Instead it maintains a manifest with:

- Source repository URL
- Path within the repository
- Pinned revision (commit/hash)

Example of Browser Use skill integration (not vendored, only referenced):

```yaml
# skills/manifest.md
- name: browser-use
  source: https://github.com/browser-use/browser-use-skill
  path: skills/browser-use
  revision: abc123def456  # pinned for reproducibility
  description: Safe browser automation patterns
```

---

## Installation & Synchronization

The goal is a single source of truth that works across multiple agents (Goose, Codex, and compatible systems).

### Local Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/blaine.git ~/workspace/blaine

# Configure local Goose to recognize skills directory
mkdir -p ~/.goose/skills
for skill in ~/workspace/blaine/skills/*.md; do
    ln -sf "$skill" ~/.goose/skills/$(basename "$skill")
done

# Verify setup
goose list-skiils  # or equivalent command
```

### Git Integration

Blaine follows its own branching policy defined in BLAINE.md:

- `main` — stable, reviewed work
- `task/<name>` — independent implementation efforts
- Use **worktrees** when multiple writers need isolation

See BLAINE.md for the complete Git and collaboration protocol.

---

## Why This Exists

Most agentic setups today suffer from:

1. **Context bloat**: Every request reconstructs what should be remembered
2. **Token waste**: Frontier models used for discovery and grep
3. **No trust boundaries**: Arbitrarily vendored skills without provenance
4. **Machine-specific chaos**: Secrets mixed with portable configuration
5. **No verification**: Builders certifying their own work

Blaine is the antidote: a local-first orchestrator that understands objectives, curates evidence deliberately, uses deterministic tools for facts, and spends frontier tokens only where they matter.

---

## Contributing to This Repository

This repository represents a working methodology. Changes should:

1. **Solve concrete problems** — no speculative abstractions
2. **Demonstrate provenance** — include commands, references, evidence
3. **Respect trust boundaries** — do not commit secrets or private data
4. **Follow existing conventions** — prefer established patterns over invention

---

## License

MIT License — permissive licensing to encourage adoption and adaptation of the orchestration patterns.

---

## Author

Leo Fuso (@leofuso)

This repository documents a personal methodology for local-first agentic development. The techniques described here are opinionated but portable.

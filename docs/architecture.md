# Blaine Architecture

This document explains the layered structure of Blaine and how each component serves a distinct purpose. Understanding these boundaries prevents drift, duplication, and confusion.

---

## Layered Architecture

```
┌──────────────────────────────────────────────┐
│              Agent Contract                  │
│           (BLAINE.md / AGENTS.md)            │
│  Defines orchestration behavior and policy   │
└──────────────────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────┐
│                 Skills                       │
│     (skills/*.md + skills/manifest.md)       │
│  Domain knowledge: testing, DDD, security    │
│  External skill references with provenance   │
└──────────────────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────┐
│               Recipes/Workflows              │
│            (recipes/*.recipe)                │
│  Reusable deterministic workflows            │
│  Only when repetition justifies automation   │
└──────────────────────────────────────────────┘
                        │
                        v
┌──────────────────────────────────────────────┐
│        Machine-Specific Configuration        │
│    (~/.goose/, .env, gitignored files)       │
│  Secrets, credentials, local paths           │
│  NEVER committed to this repository          │
└──────────────────────────────────────────────┘
```

---

## Layer 1: Agent Contract (BLAINE.md)

**Purpose:** Defines the orchestration agent's behavior and decision-making framework.

**Location:** `BLAINE.md` (canonical), `AGENTS.md` (symlink for Codex compatibility)

**Content:**
- Operating principles
- Triage methodology
- Local-first routing policy
- When to delegate vs. stay local
- Completion states and handoff protocols
- Safety boundaries

**Why it exists:** Every agent invocation should behave consistently. This layer is the "constitution" — high-level policy that guides all downstream behavior.

**Changes are justified when:**
- The orchestration methodology fundamentally changes
- New completion states or handoff patterns are needed
- Triage criteria evolve based on real-world usage

---

## Layer 2: Skills (`skills/`)

**Purpose:** Portable, reusable domain knowledge that agents can load contextually.

**Location:** `skills/*.md` files (e.g., `JAVA_TESTING.md`, `DDD_MODELING.md`)

**Content:**
- Concrete commands and patterns
- Verified examples with expected outputs
- Tool requirements and version constraints
- Known limitations and failure modes

**What skills are NOT:**
- Not agent policy or behavior definitions
- Not machine-specific configuration
- Not arbitrary external skill copies (use manifest references instead)

**External Skills Manifest (`skills/manifest.md`):**
- References to trusted external skills
- Pinned revisions for reproducibility
- Trust boundary documentation

**Why it exists:** Skills allow agents to load just-in-time expertise without bloating the core contract. A Java testing skill should work on any machine with the right setup, independent of Blaine's orchestration logic.

---

## Layer 3: Recipes/Workflows (`recipes/`)

**Purpose:** Deterministic, repeatable workflows that justify automation.

**Location:** `recipes/*.recipe` or similar format

**Content:**
- Step-by-step automation for repetitive tasks
- Project scaffolding
- Multi-project operations
- CI/CD configuration generation

**When recipes ARE justified:**
- The workflow is performed 3+ times independently
- Steps are deterministic and tool-based
- Human judgment is minimal during execution

**When recipes are NOT justified:**
- One-off tasks (just use a shell script)
- Highly variable workflows
- Tasks requiring significant human decision-making

**Why it exists:** Recipes codify successful patterns into reusable automation. If you're manually repeating the same steps across projects, a recipe prevents drift and errors.

---

## Layer 4: Machine-Specific Configuration

**Purpose:** Local credentials, paths, and private settings that vary per machine.

**Location:** Gitignored directories (`~/.goose/`, `.env.local`, `./.local/`)

**Content:**
- API keys and tokens (NEVER committed)
- Absolute local paths
- Personal notes or project-specific secrets
- IDE/editor configurations

**Why it exists:** This layer is explicitly excluded from the repository. Public code should never contain secrets, and personal configuration shouldn't pollute portable artifacts.

**Gitignore coverage:**

```gitignore
# Secrets and credentials
.env*
*.key
*.pem
secrets/

# Local machine config
.local/
~/.goose/local-config/*

# Editor/IDE state
.idea/
.vscode/
*.swp
*.swo

# Logs and temporary files
*.log
tmp/
*.tmp
```

---

## Decision Matrix: Where Does X Belong?

| Artifact | Agent Contract | Skills | Recipes | Machine Config |
|----------|---------------|--------|---------|----------------|
| "When to delegate frontier work" | ✅ | | | |
| "JUnit 5 test patterns" | | ✅ | | |
| "Spring Boot project bootstrapping" | | | ✅ (if repetitive) | |
| API key for external service | | | | ✅ |
| Local path `/home/leo/src` | | | | ✅ |
| DDD aggregate design principles | | ✅ | | |
| Trust boundary for external skills | | ✅ (manifest.md) | | |
| CI pipeline configuration template | | | ✅ | |

---

## How Layers Interact

### Example Workflow: Java Testing Task

1. **Agent Contract (BLAINE.md)** receives task: "Add integration tests to Spring Boot service"
2. **Triage**: Local-first investigation — inspect code structure, understand architecture
3. **Load Skill**: `load_skill(name: "spring-boot-testing")` brings in JUnit/Testcontainers patterns
4. **Execute Locally**: Run deterministic tools (`mvn test`, docker container inspection)
5. **Delegate if Needed**: Complex architectural change → frontier worker with curated context packet
6. **Verify**: Pass tests, ensure expected behavior matches evidence
7. **Complete**: Report with state DONE and traceable evidence

### Example Workflow: External Skill Integration

1. **Identify Need**: Require browser automation capability
2. **Consult Manifest**: Check if already referenced in `skills/manifest.md`
3. **Evaluate**: Review external skill for security, side effects, provenance
4. **Add Reference**: If trusted, pin specific revision and add to manifest
5. **Do Not Vendor**: Use reference only; avoid duplicating content that can drift

---

## Portability Goals

This repository should work across:
- Multiple machines (yours, team members')
- Different Goose installations
- Compatibility with Codex via AGENTS.md symlink
- Future agent frameworks that understand Markdown contracts

Portability is achieved by:
- Separating policy from configuration
- Using relative paths where possible
- Documenting requirements rather than assuming environment
- Maintaining trust boundaries (what can drift vs. what must be pinned)

---

## Trust Boundaries Summary

| Boundary | Description | Risk Level |
|----------|-------------|------------|
| Agent Contract | Defines system behavior; authored locally | Internal control |
| Local Skills | Authored domain knowledge in this repo | Internal control |
| External Skills Manifest | References external sources with provenance | Trusts referenced source |
| Machine Config | Per-machine, never shared | Isolated from public |

**Key principle:** This repository is the portable truth. Machine-specific and private configuration stays out. External references are documented but never blindly vendored.

---

## Maintenance Model

- **BLAINE.md**: Updated only when orchestration methodology changes
- **Skills**: Evolve independently as tools, frameworks, conventions shift
- **Recipes**: Created ad-hoc when repetition justifies automation
- **Manifest**: New entries require evaluation and pinning; existing entries may update revision if re-evaluated

Each layer can change at its own pace without cascading breaking changes.

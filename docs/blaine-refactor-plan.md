# Blaine Refactor Plan — Rule Classification

Classification of every rule, section, and practice in `BLAINE.md` versus upstream `CLAUDE.md`, and a plan for splitting the result into coherent files.

## Legend

| Tag      | Meaning                                                             |
|----------|---------------------------------------------------------------------|
| **CORE**  | Keep as core principles — identity, safety, universal judgment rules. |
| **POLICY** | Keep but pull out into separate policy files (≤ 6 total).            |
| **SKILL** | Candidate for a skill / recipe / template rather than inline prose. |
| **OMIT**  | Do not carry forward. Too project-specific, redundant, or noisy.     |

---

## Section-by-section classification

### 1. Purpose (BLAINE: §1)
- **CORE** — Identity as local coordinator; frontier-scarce thesis.
- Upstream has an equivalent "How to work" mindset block with similar ethos (Claude Code, token discipline). The Blaine framing (local-cost-aware) is the only relevant version for this project.

### 2. Core operating principles (§1-8)
- **CORE** — Eight axioms: understand-before-delegating, direct-over-inference, curate-deliberately → use-deterministic → search-before-building → activity!=progress→finish-task → make-uncertainty-visible. These are the bedrock; nothing to split out.

### 3. Triage before spending compute (§1)
- **POLICY** — Size/risk/worktype/execution/verification/budget classification + size thresholds (small / medium / large). The upstream version is more prescriptive (mandatory four-line triage block, explicit testing branching), but the Blaine version's compact labels are cleaner. Keep; merge upstream additions as an optional triage-template appendix.

### 4. Local-first routing policy (§1)
- **POLICY** — "When to keep local vs delegate" criteria + Codex as named primary frontier worker + one-call-over-pingpong principle. The upstream equivalent ("LLM access — local Code, not the API") has a concrete architecture decision (self-contained LLM service under `services/llm/`). That architectural detail is useful; carry it in here.

### 5. Context engineering and delegation packets (§1)
- **POLICY** — Delegation-packet template (Objective / Context / Evidence / Scope / Constraints / Acceptance / Uncertainties / Requested output), bias warning for critics, provenance preservation, secret exclusion. Upstream has equivalent ideas scattered in "The context window is the lever" and several policy blocks. Keep; unify with upstream context-curation prose.

### 6. Deterministic space vs latent space (§1)
- **CORE** — The meta-loop ("LLM writes script → script constrains LLM") is a fundamental Blaine insight, not a project policy. Keep in-place as CORE.

### 7. Tools, MCPs, and capability acquisition (§1-2)
- **POLICY** — Preference hierarchy (local tool → configured MCP → established server → small script → custom infra) + trust verification + user-scoped install rules. Upstream equivalent: "Tech choice — vanilla by default" + "Search before building" (3-layer evaluation). Merge the 3-layer search into this block.
- **SUB-SECTION: Authentication and human handoff** → **POLICY**. Standalone section is important; keep.

### 8. Multi-agent orchestration (§1-2)
- **POLICY — §8a Readers vs writers / Variant tournaments / Builder-critic separation.** Keep in a file but trim the upstream "harsh critic" prose to Blaine's restraint level (we deliberately moved away from the "harsh by default" ritual). Keep variant-tournament guidance; drop the specific `/tmp/<task>/critique/` artifact paths and the three-pass blind-labelling as procedural detail (too heavyweight for Blaine's scope).
- **POLICY — §8b Fan-out decision.** "When to fan out" lives with Triage. Cross-reference only.

### 9. Git, branches, and worktrees (§1)
- **OMIT** — The safety bullets (protected branches, git status before write, one-task-branch, separate trees for concurrent writers, no force-push on shared branches) are good default rules; keep those as a short CORE list.
- **The rest is OMIT.** Worktree setup script, Claude Code session injection, `claude.mode` config, bootstrap procedure (`.env` copy, `node_modules` symlink), PR lifecycle (rebase→push→force-with-lease→gh pr create), sweep/cleanup commands are all Claude Code/Julien-specific. Carrying these into Blaine is project lock-in. The upstream branching ritual (~70 lines of bash) is the bulk of this section and is not portable to Goose's extension/session model.

### 10. Coding and engineering quality (§1)
- **CORE** — "Understand architecture → search patterns → simplest tech → observable outcome → blast-radius testing → regression tests for bugs → full suites for broad risk → doc updates." Upstream equivalent: "Quality first, length second" + "Tie every change to a measurable outcome". Merge the measurability language from upstream here.

### 11. Long-running and background work (§1-2)
- **POLICY** — Monitoring cadence, deterministic ETA derivation, rollback/recovery planning. Upstream adds snapshot-before-touch, CSV diff report, `/tmp/<job-name>/progress.log`. The monitoring core is good; the upstream bash-heavy details (line counts, 100k/100MB thresholds) are project-specific procedural noise. Keep the principles; drop implementation details.

### 12. Safety boundaries (§1)
- **CORE** — Seven "Never" rules + private-material policy. Upstream equivalent: Safety section with overlapping bullets (no secrets, no destructive ops without confirm, pre-commit hooks, no binaries, production confirmation). Merge into one clean CORE safety block.

### 13. Confusion protocol (§1)
- **CORE** — When to pause and ask the human. Upstream equivalent is compact and identical in substance. Keep; minor merge of additional trigger examples if useful.

### 14. Completion and human-interaction states (§1)
- **POLICY.** Six states: DONE, DONE_WITH_CONCERNS, BLOCKED, NEEDS_CONTEXT, NEEDS_AUTH, NEEDS_APPROVAL. Upstream adds self-rating protocol (score 1–10, loop until yes, drift-guard to fresh critic). The core state machine is universal; the self-rating protocol is Claude Code ritual. **Split:** keep states as POLICY; drop score/loop as OMIT for Blaine's scope. Mark as a potential future SKILL if Goose adds evaluators.

### 15. Final verification and self-review (§1-2)
- **CORE** — Fresh-read-before-completion, medium/large multi-step check, converge quality-loops. Upstream equivalent is the self-rating protocol; the verification logic that remains is good practice. Keep as CORE.

### 16. Communication style (§1-2)
- **SKILL.** This is a personal style preference for Julien's communication (direct, no AI vocabulary, specific identifiers). For Blaine, keep only the universal sub-rules: direct/concrete/economical; distinguish fact from inference; surface orchestration choices; end with next action when required. Move the banned-Vocabulary / banned-phrases list to OMIT — it is personal style for a specific human.

### 17. Frontier delegation telemetry (§1-2)
- **OMIT** — Recording worker/provider/model/tokens/duration/etc. is tooling-dependent and noise-prompt. The insight ("optimize for useful work, not token counts") is already in the Purpose block. Drop. If Goose has a billing/telemetry layer that can surface this automatically, implement it as an extension.

---

## Proposed policy file set (5 files)

| # | File | Contents |
|---|------|----------|
| 1 | `docs/policies/triage-routing.md` | Triage classification matrix + size thresholds + execution/verification mappings + confusions between sizes. Cross-reference to Local-First here. |
| 2 | `docs/policies/local-first-and-context.md` | When to keep local vs delegate; deterministic-over-latent rule; delegation-packet template; provenance & secret rules. |
| 3 | `docs/policies/tools-and-capability.md` | Tool/MCP preference hierarchy; search-before-building (3 layers); trust verification; user-scoped install gates; authentication handoff states. |
| 4 | `docs/policies/orchestration.md` | Multi-agent fan-out decision tree (when to vs when not); reader/writer isolation rules; variant-tournament eligibility; builder-critic separation; quality-loop stall rule. |
| 5 | `docs/policies/task-completion-and-lifecycle.md` | Completion/interaction state machine (the six states); verification-pass rules for each state; long-running job monitoring principles; rollback/recovery planning requirement. |

All other policies are absorbed into **CORE** (§1 Purpose, §2 Core principles, §6 Deterministic vs latent, §10 Coding quality, §12 Safety, §13 Confusion protocol, §15 Final verification).

---

## Summary of classification counts

| Tag      | § count | What it captures |
|----------|---------|------------------|
| **CORE**  | 7 (Pur + CorePrin + Deterministic + CodingQ + Safety + Confusion + Verification) | Identity, safety gates, fundamental reasoning rules, engineering quality. |
| **POLICY** | 5 files (see table above) | Decision frameworks: triage+routing, local-first+delegation context, tool selection, orchestration multi-agent, task lifecycle+states. |
| **SKILL** | 1 category (Communication style universal sub-rules) | Style rules; rest is personal to Julien — move to OMIT. |
| **OMIT**  | ~6 sections / practices | Claude-specific worktree/PR/cleanup bash, harsh-critic blind rituals, telemetry recording, Julien's banned vocabulary/phrases, self-rating score loop, upstream project-locking procedural details. |

### Net result

- **From ~17 sections + extensive prose → CORE (identity/safety/quality) + 5 policy files.**
- The total rule count decreases because Claude-specific rituals, bash scripts, and personal style preferences are dropped.
- No useful Blaine capability is lost; the upstream additions that *are* portable (measurable-outcome requirement, search-before-building layers, snapshot/rollback principle for background jobs) are folded into the relevant policy file or CORE block.

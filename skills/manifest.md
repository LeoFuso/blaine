# External Skills Manifest

This manifest defines trusted external skills referenced by this repository. External skills form a **trust boundary** — arbitrary community skills should not be vendored without review and provenance tracking.

Each entry specifies:
- `name`: Identifier for the skill
- `source`: Repository URL (GitHub, or other Git host)
- `path`: Path within the source repository
- `revision`: Pinned commit hash or tagged version for reproducibility
- `description`: What the skill provides
- `integration_notes`: How it should be used or any caveats

---

## Current References

No external skills are currently adopted.

External skills must be evaluated and pinned to a specific revision before being added here.

---

## Candidates Under Evaluation

### Browser Use

Browser automation is a candidate capability for future integration.

**Status:** Not yet evaluated or adopted.

Before adoption:

- identify the authoritative implementation;
- review its security and trust boundaries;
- evaluate sandboxing and network behavior;
- confirm license compatibility;
- pin the exact source, path, and revision;
- document integration constraints.

Do not treat candidates in this section as trusted or installed capabilities.

---

## How to Add a New External Skill Reference

1. **Evaluate the skill independently**: Understand what it does, any side effects, and whether it follows security best practices.
2. **Pin a specific revision**: Never reference `main` or floating branches — commits diverge.
3. **Add entry above** with full provenance (source, path, revision).
4. **Document integration notes**: Any special usage patterns, constraints, or warnings.
5. **Consider local fork**: If you make modifications, note whether this repository uses a fork or patches.

---

## Review Policy

Before adding an external skill:

- [ ] Source is authoritative (maintained, not abandonware)
- [ ] No hidden network calls or data exfiltration (read the implementation)
- [ ] No unexpected side effects (file writes, network requests beyond its scope)
- [ ] Pinned to a specific revision for reproducibility
- [ ] License is compatible with this repository's license

---

## Integration Methods

Skills can be integrated in three ways:

1. **Reference only** — document where it comes from, use via original source
2. **Symlinked/fetched at sync time** — pulled into local skills directory during synchronization
3. **Vendored with attribution** — copied verbatim with clear provenance (only when necessary)

This repository prefers **reference-only** integration to avoid drift between this copy and the authoritative source.

---

## Machine-Specific Configuration

Do **not** store credentials, API keys, or machine-specific paths in this file. Those belong in:

- `~/.goose/skills/config.yaml` (Goose-specific)
- Environment variables
- Secrets manager (if applicable)

This manifest is intentionally public and contains only references to external resources.

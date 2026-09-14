# Skill convention

Each local skill lives in `skills/<name>/SKILL.md` with YAML frontmatter containing
`name` and a concise `description` of when to use it. Each has one responsibility.
This file is an authoring convention, not an executable skill.

Discover skills through [BLAINE.md](../BLAINE.md); load only the selected skill
and needed references. Shared contracts live in `docs/contracts/`, policy in
`docs/policies/`. Do not copy either into each skill.

Personal Agent skills define behavior and future binding requirements. They do not
install tools or implement durable execution. No loader or adapter is implied.
Add commands only when real bindings exist and commands have been verified.

External skills follow [manifest.md](manifest.md): reviewed provenance, pinned
revisions, and explicit trust boundaries. Private configuration stays outside
this public repository.

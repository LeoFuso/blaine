# Agent Skills Convention

This document defines the convention for authoring and organizing agent skills in this repository. Skills are reusable capabilities that agents can load to perform specific tasks more effectively.

---

## What Is a Skill?

A skill is a **self-contained Markdown file** that defines:

- **Purpose**: What task or domain it addresses
- **Requirements**: Dependencies, tools, or environment setup needed
- **Usage**: How to invoke the skill with concrete examples
- **Constraints**: Limitations, edge cases, and failure modes
- **Evidence**: Commands, tests, or observations that verify the skill works

Skills are designed for consumption by LLM-based agents (Goose, Codex, etc.) to provide context for specific domains without cluttering core agent instructions.

---

## Skill File Structure

Each skill should follow this template:

```markdown
# <skill-name>

## Purpose

What problem does this skill solve? What domain does it cover?

## Requirements

List any dependencies, tools, or configuration needed:
- Tool/dependency 1
- Tool/dependency 2

### Verify Setup

Include a command to verify the environment is ready:

```bash
which some-command && some-command --version
```

## Usage

Show concrete examples of how to use this skill. Include:
- Typical invocations
- Parameters and their meanings
- Expected outputs

### Example 1: Basic Usage

Description of what this example demonstrates.

**Command:**
```bash
# Show the exact command or workflow
some-command --option value
```

**Expected output:**
```
What a correct execution looks like
```

## Patterns and Conventions

Document established patterns, conventions, or best practices:
- Pattern 1
- Pattern 2

## Constraints and Failure Modes

What can go wrong? Document:
- Known limitations
- Edge cases
- What to do when things fail

## References

- Links to documentation
- Related skills
- Original source if adapted from elsewhere

---
Generated-by: <agent/model> (if created by automation)
```

---

## Skill Categories

Skills in this repository fall into these categories:

| Category | Description | Examples |
|----------|-------------|----------|
| **Testing** | Testing frameworks, patterns, and methodologies | Java testing, Spring Boot integration tests |
| **Architecture** | Design patterns, DDD principles, modeling approaches | Domain-driven design, layered architecture |
| **Tooling** | Development tools, CLI patterns, automation | Git workflows, build tools |
| **Security** | Security practices, review checklists, threat modeling | OAuth flows, secrets management |

---

## Authoring Guidelines

1. **Be concrete**: Include exact commands, file paths, and outputs
2. **Verify before committing**: Run the documented commands yourself
3. **Version awareness**: Note version-specific behavior (e.g., "Spring Boot 3.x+")
4. **No secrets**: Never include credentials or private keys in examples
5. **Trace provenance**: If adapted from elsewhere, cite the source
6. **Keep atomic**: One skill per file, focused on a single capability

---

## Loading Skills (Goose Integration)

Skills are loaded dynamically by agents:

```bash
# Load a specific skill
load_skill(name: "spring-boot-testing")

# Load with arguments
load_skill(name: "ddd-modeling", args: "<entity-type>")

# Load supporting files
load_skill(name: "skill-name/support-file.md")
```

From this repository, skills can be synchronized to the agent's local skill directory:

```bash
# Synchronize all skills from this repository
for skill in ~/workspace/blaine/skills/*.md; do
    ln -sf "$skill" ~/.goose/skills/$(basename "$skill")
done

# Synchronize a single skill
ln -sf ~/workspace/blaine/skills/spring-boot-testing.md ~/.goose/skills/spring-boot-testing.md
```

---

## Skills vs. Recipes

**Skills** provide domain knowledge and capabilities:
- What Java testing patterns exist
- How to structure DDD aggregates
- Security checklist items

**Recipes** (in `recipes/`) are executable workflows:
- Boilerplate project setup
- CI configuration generation
- Batch operations

Think of skills as **knowledge** and recipes as **actions**.

---

## Skills vs. External References

Local skills contain first-class, authored content. External skills are referenced in [`manifest.md`](manifest.md) with pinned revisions. Do not duplicate external skill content here — maintain the reference instead.

---

## Example: Java Testing Skill (Skeleton)

```markdown
# Java Testing

## Purpose

Java unit and integration testing patterns using JUnit 5, Mockito, and Testcontainers.

## Requirements

- JDK 17+
- Maven or Gradle
- Docker (for Testcontainers)

### Verify Setup

```bash
java --version && mvn --version && docker --version
```

## Usage

### Unit Testing with JUnit 5

Write unit tests with parameterized inputs:

```java
@ParameterizedTest
@CsvSource({"1,2,3", "4,5,9"})
void testAddition(int a, int b, int expected) {
    assertEquals(expected, calculator.add(a, b));
}
```

### Integration Testing with Testcontainers

Spin up ephemeral databases:

```java
@Testcontainers
class UserRepositoryTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15");

    @BeforeEach
    void setup() {
        // Use postgres.getJdbcUrl() for connection
    }
}
```

## Constraints

- Testcontainers requires Docker daemon to be running
- Slow integration tests should be excluded from PR checks (use `@Disabled` or test profiles)

## References

- [JUnit 5 User Guide](https://junit.org/junit5/docs/current/user-guide/)
- [Testcontainers Documentation](https://testcontainers.com/)
```

---

## Maintenance

As skills are created and evolved:

1. **Update this document** if conventions change
2. **Review for drift**: Periodically check that examples still work with current tool versions
3. **Deprecate gracefully**: Mark outdated skills rather than deleting them (rename to `<skill>.deprecated.md`)

---

This convention is adapted from common patterns in agent workflows and Goose skill documentation systems. It emphasizes reproducibility, traceability, and machine-actionable content.

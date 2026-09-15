# Tools and capability acquisition

Task capabilities describe required access, not installed tools or permission grants.
Prefer existing local tools and configured integrations, then established trustworthy
packages, then small deterministic scripts. New infrastructure needs a concrete gap.
Do not assume a specific worker or MCP provider is present.

Before acquiring a dependency, verify canonical provenance, requested permissions,
data access, and whether a standard tool already fits. Grant only required scopes.
External skill adoption follows [the manifest](../../skills/manifest.md).

Lightweight reversible user-scoped installs may proceed within existing Task and
host permissions. System-wide changes, new network listeners, broad account scopes,
unverified sources, and changes without clean removal require scoped authorization.
Acquisition for durable work runs through runtime-managed execution, not a separate
Personal Agent lifecycle.

## Authentication handoff

Use the tool's native secure login, OAuth/device flow, or OS credential store.
Never request passwords, private keys, recovery codes, or long-lived tokens in chat.
If human interaction is required, expose the runtime's waiting condition and exact
secure action. Confirm access through the tool before requesting continuation;
a user's acknowledgment alone is not proof that authentication succeeded.
For remote sessions, ensure callbacks reach the intended host within authorized
access boundaries. Runtime owns waiting and resumption; see
[lifecycle policy](task-completion-and-lifecycle.md).

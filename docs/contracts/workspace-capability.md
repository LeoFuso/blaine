# E1 workspace capability — IDE-delegated read-only design contract

**Status: DESIGN, not implemented (2026-09-23).** Decision rationale (Accepted):
[ADR 0027](../decisions/0027-ide-delegation-is-workspace-authority.md). This
contract revises the E1 provider in the [Hub design](../personal-agent-hub.md#e1--remote-workspace-read)
and is the first consumer of [Completion Contract v1](completion-contract.md).
No workspace capability, protocol frame or client change described here exists yet.

E1 goal: a durable Blaine Task obtains evidence from a selected workstation
workspace, through the capability surface the operator delegated in IntelliJ,
while its effective authority is READ_ONLY and the capability journal proves that
no mutating capability was admitted or executed.

## Authority model

Four concepts, deliberately separate:

| Concept | Meaning | Owner / source | E1 representation |
| --- | --- | --- | --- |
| **Delegated scope** | Projects and capabilities IntelliJ exposes to Blaine | Operator: installing Blaine as a JetBrains ACP agent with **Pass IntelliJ MCP server** (`use_idea_mcp`) enabled for that agent (see [onboarding](#delegation-onboarding)) | `DelegationSnapshot` observed per ACP session |
| **Task relevance** | Which delegated project/context this Task works in | Context Plane resolution ([Resolver](../context-plane.md#11-workspace-knowledge-and-routing)); until Context Plane integration, the project the chat is attached to or one the user names | `workspace_id` in the Task request |
| **User constraints** | Operator policy such as Read Only, approvals, model preference | Delivered through ACP `configOptions` (an input channel, not a policy engine) and explicit Task signals | Recorded in the trusted envelope |
| **Effective authority** | What this Task may actually do | Compiled by Blaine; **enforced only by PolicyGate** | `EffectiveAuthority` artifact + grant |

There is one Blaine authority model with several policy inputs. JetBrains
configuration, ACP `configOptions` and the local client supply inputs or transport;
none evaluates Task authority.

```text
effective authority = Task grant (operation classes requested for this Task type)
                    ∩ user constraints (e.g. access = read_only)
                    ∩ delegated scope (projects + tools observed in the bound session)
                    ∩ Blaine operation classification (unknown tool ⇒ no class ⇒ denied)
```

Consequences:

- Installing Blaine as an IntelliJ agent with `use_idea_mcp` enabled **is** the
  operator's delegation. Blaine adds no second workspace approval, consent file or
  prompt, including when IntelliJ exposes several open projects. Where the Hub
  design, ADR 0022 or the Context Plane speak of "workspace consent" for an
  IntelliJ-provided workspace, this delegation is that consent.
- Relevance is not authorization. The Context Plane selects which delegated
  project a Task needs; PolicyGate decides what the Task may do there.
- An ACP `resource_link` is a context reference inside the delegated scope: a
  locator hint for Context Plane resolution and for workspace operations, never
  additional authority, never evidence by itself, and never a reason for another
  prompt.
- The local `blaine acp` client is a protocol/capability **bridge**: protocol
  validity, session/correlation correctness, forwarding, local token
  confidentiality and receipt transport. It does not filter, project or
  re-authorize the delegated tool set. PolicyGate on the Hub is the single
  enforcement authority. Protocol integrity is not Task authorization.
- READ_ONLY is not implemented by hiding tools. The delegated MCP surface may
  contain mutating tools; E1 proves that a READ_ONLY Task never invokes them.

### Delegation onboarding

Hub connectivity and JetBrains integration are separate operations:

| Operation | Owns | JetBrains configuration |
| --- | --- | --- |
| `blaine connect` | Enrollment, Hub discovery, identity and readiness | Never touched |
| `blaine integration jetbrains install` (also invoked by the public/development installer) | Registering Blaine as a JetBrains ACP agent | Merges the owned Blaine entry **and sets `use_idea_mcp = true` for that entry** |
| `blaine integration jetbrains check` / `blaine doctor` | Read-only verification | Reports whether the Blaine entry exists, matches, and has MCP delegation configured |

Installing Blaine as an IntelliJ agent is the explicit operator act that grants the
IDE-exposed project surface, so no separate manual toggle is required. The install:

- sets the **per-agent** override for the Blaine entry only, preserving
  `default_mcp_settings` and every other agent's MCP exposure. It never enables the
  global default. `use_custom_mcp` stays off for Blaine;
- keeps the existing merge guarantees (duplicate/structure rejection, backup,
  atomic replace, concurrent-edit check, identical config not rewritten);
- reports honestly when the installed IDE offers no per-agent override: delegation
  is then *not configured* and E1 capabilities are unavailable. It does not fall
  back to changing global defaults, because that would delegate to other agents.

JetBrains documents that agent-specific MCP settings override
`default_mcp_settings` but not the per-entry key name. E0.E/E1.A records the key
the installed IDE writes when the per-agent option is toggled, then freezes it
with fixtures. Today's installer writes `use_idea_mcp: false` into
`default_mcp_settings` when it creates a new file; that changes with this design.
An operator who does not want to delegate turns the per-agent option off in the
IDE; workspace operations then report UNAVAILABLE with that reason.

### Security model

For the current personal deployment:

- The operator trusts the Blaine Hub; it is part of the trusted computing base.
- IntelliJ is a broad capability provider. The delegated MCP surface may include
  read, search, symbol lookup, write, terminal, run configurations, debugger,
  database and other IDE tools. That breadth is acceptable and is not hidden locally.
- Tailscale/tsnet protects private connectivity and device admission; E0.D provides
  workstation identity, inventory and presence.
- Task authority and PolicyGate on the Hub are the authoritative application policy
  boundary and control operation scope. The workstation client does not
  independently re-evaluate Task authority.
- **Accepted residual:** a compromised Hub is outside the protection offered by
  Task-level PolicyGate and could invoke any delegated IntelliJ tool, subject only
  to IntelliJ's own controls (exposed-tool settings; command confirmation unless
  "brave mode" is on). This residual is accepted for the current threat model; no
  local authorization engine is added to defend against it.
- The client still enforces protocol integrity: framing, size and deadline bounds,
  JSON-RPC and operation correlation, session binding, and keeping IDE tokens on the
  workstation. These protect the channel, not Task authority.

## Verified IntelliJ MCP semantics

Checked 2026-09-23 against JetBrains documentation and `intellij-community`
source (`plugins/mcp-server`). These are observations of the upstream
implementation, to be re-confirmed against the installed IDE in E1.A.

| Property | Observed behavior | Design consequence |
| --- | --- | --- |
| Delegation to ACP agents | "Pass IntelliJ MCP server" (`use_idea_mcp`, default **false**), overridable per agent (per-entry key undocumented); the IDE passes MCP servers in ACP `session/new` `mcpServers` | Set per agent by the integration install; recorded as the delegation event. E0.C's real session sent none, consistent with the default |
| Endpoint | Loopback HTTP (SSE/streamable) or stdio runner; an isolated "authorized session" server uses a per-session token header | The Hub cannot reach it; the workstation client must bridge. Tokens stay on the workstation |
| Project selection | IDE-global server; per call: `projectPath` argument (strict), else call header, session header (`IJ_MCP_SERVER_PROJECT_PATH`), else MCP roots | Delegated scope may contain several open projects; Task relevance must pick one explicitly |
| Search tools | `search_text`, `search_regex`, `search_file`, `search_symbol` search the project index scope and return project-relative results; excluded/external content off by default | Provider for the Context Plane's lexical/symbol workspace search on a remote workspace, without a Blaine search engine |
| `list_directory_tree` | Lexically rejects paths outside the project directory | IDE boundary |
| `read_file` | Resolves relative or absolute paths/VFS URLs, then refuses files outside "project, library, and SDK roots"; returns the IDE **document** (may include unsaved edits), line-windowed | IDE boundary includes dependency sources; evidence is labelled `ide_document`, not a disk hash |
| Mutating / executing tools | Same server exposes `create_new_file`, `apply_patch`, `rename_refactoring`, `reformat_file`, `execute_terminal_command`, `execute_run_configuration`, `build_project`, database and debugger tools; tool enablement is an IDE-global setting | Present in delegated scope; excluded from READ_ONLY effective authority by PolicyGate, not by the bridge |
| Tool annotations | Tools carry `readOnlyHint` | Provider self-description; an input to Blaine's classification review, never authority |

Unverified until E1.A records a redacted real `session/new`: which endpoint form
AI Assistant passes to a custom agent (authorized session vs global server, HTTP vs
stdio), whether it sets the project header, and the installed tool list.

## Workspace

A Workspace is **Blaine's representation of an IDE project available from one
registered workstation**. It is not a filesystem mount, and Blaine never resolves
its paths on the Hub.

```text
workspace_id = "wsp-" + first 128 bits of SHA-256(
                 workstation_id, path_platform, canonical project base path)
```

`workstation_id` is the Hub-assigned E0.D inventory ID bound to the authenticated
tailnet node ([workstation identity](workstation-identity.md)); it is carried into
the ACP adapter environment as E0.D's routing hook.

| Question | Answer |
| --- | --- |
| Which workstation provides it? | The E0.D `workstation_id` in its identity. The same repository on two workstations is two Workspaces |
| Which IntelliJ project does it represent? | The project base path IntelliJ reports for the session (ACP `cwd`, confirmed against the MCP project), canonicalized on the workstation; IDE product/build and project name are descriptive metadata |
| Is it currently available? | Derived, never stored as authority: E0.D presence for the workstation (ONLINE/OFFLINE lease) **and** a live ACP session whose `DelegationSnapshot` lists the project. ONLINE alone is not availability |
| Which Tasks operate on it? | Tasks record `workspace_id` in their authority and receipts; answered by Task queries. No separate Workspace-to-Task registry |
| Durable identity | Derived deterministically; no Workspace registry or approval record is required for E1 |
| Several per workstation | Yes: every project the delegating IDE exposes is delegated scope, with no per-project approval |
| Survives IDE/session restart | Yes. Identity depends only on workstation and root; routes are ephemeral |
| Unavailable | The Task keeps its `workspace_id`; operations wait (see [disconnect](#disconnect-and-reconnect)) |
| Project moved/re-rooted | Different `workspace_id`. Retargeting an existing Task is an explicit user amendment, not automatic |

E0.D is PASS, so E1 uses the server-assigned `workstation_id` directly. The
Workspace may later appear as an E0.D inventory association for display; E1 needs
no new table, and nothing in that association would grant access.

### DelegationSnapshot

Recorded by the Hub when a session is established, as an artifact referenced by
Tasks that use it. It contains no token, URL secret or file content.

```json
{"version": 1, "kind": "DelegationSnapshot", "payload": {
  "workstation_id": "ws-…", "session_id": "…",
  "ide": {"product": "IU", "build": "262.10968.63", "ai_assistant": "262.10968.97"},
  "provider": {"kind": "intellij-mcp", "transport": "http", "server_version": "…"},
  "projects": [{"workspace_id": "wsp-…", "root": "/home/alex/src/orchid-service",
                "path_platform": "posix", "source": "acp_cwd"}],
  "tools": {"names": ["read_file", "search_text", "apply_patch", "…"], "list_sha256": "…"},
  "observed_at": "2026-…Z"}}
```

A later session produces a new snapshot. A Task never uses a snapshot as current
permission after its session ends; each dispatch re-checks against the snapshot of
the live route it is sent through.

## Effective authority

### User constraints through ACP configOptions

Blaine advertises session config options; IntelliJ renders them and returns the
selection through `session/set_config_option`. Blaine treats the selection as an
operator constraint and compiles it; there is no policy engine in the option layer.

E1 advertises exactly one enforceable option value, because Blaine must not
advertise a mode it cannot enforce ([Hub future session controls](../personal-agent-hub.md#future-session-controls-in-the-ide)):

| Option | E1 values | Compiles to |
| --- | --- | --- |
| `access` | `read_only` (only value) | `operation_classes ⊆ {workspace.read}` |

E2 adds values such as `edit_with_approval`, compiling to `workspace.write` plus
`autonomy.ask_before`. The selected value is captured into the trusted Task
envelope at creation. Narrowing an option while a Task runs applies to that Task
at its next dispatch; widening never changes an existing Task (only a new Task, or
an explicit `modify-constraints` signal).

### Compiled authority

```json
{"version": 1, "kind": "EffectiveAuthority", "payload": {
  "task_id": "task-…", "revision": 0,
  "operation_classes": ["workspace.read"],
  "workspaces": ["wsp-…"],
  "constraints": {"access": "read_only", "source": "acp_config_option"},
  "delegation_ref": "artifact://…", "classification": "intellij-mcp@1"}}
```

Retained before the first effect and referenced from every capability journal
entry. The existing `grant.capabilities` carries the operation classes, so current
`effective_capabilities()` intersection logic is reused.

### Operation classification

Blaine owns a reviewed, versioned table mapping provider operations to operation
classes. It lives in Hub code next to PolicyGate, not in the client.

| Class | `intellij-mcp@1` operations | E1 |
| --- | --- | --- |
| `workspace.read` | `read_file`, `list_directory_tree`, `search_text`, `search_regex`, `search_file`, `search_symbol` | Admissible under READ_ONLY |
| `workspace.write` | `create_new_file`, `apply_patch`, `rename_refactoring`, `reformat_file` | Denied (no class in E1 authority) |
| `workspace.exec` | `execute_terminal_command`, `execute_run_configuration`, `build_project` | Denied |
| unclassified | everything else, including database, debugger, UI (`open_file_in_editor`) and any unknown tool | Always denied |

Unclassified means denied under every authority, so a new IDE tool cannot be used
until Blaine reviews it. Candidates for a later `workspace.read` extension after
review: `get_symbol_info`, `analyze_calls`, `get_project_modules`, `git_status`.

## Operation contract

The model proposes; code lowers; PolicyGate admits. The existing `workspace.read`
capability name is reused with a versioned input form. The D2 exact-path form
(`{workspace, path, artifact}`) remains accepted as the legacy D2 fixture variant.

**Cognition proposal** (`INVOKE_CAPABILITY`):

```json
{"type": "INVOKE_CAPABILITY", "capability": "workspace.read",
 "input": {"form": "provider_call", "workspace_id": "wsp-…",
           "operation": "search_text", "arguments": {"q": "customerStatus", "limit": 20}}}
```

**PolicyGate admission** (Hub, deterministic, all must hold):

1. `workspace.read` ∈ effective operation classes; `operation` classifies to
   `workspace.read` under the pinned classification version.
2. `workspace_id` ∈ `EffectiveAuthority.workspaces`, and the live route's
   `DelegationSnapshot` lists that workspace and that operation.
3. Arguments validate against a per-operation schema: path arguments are
   workspace-relative (no absolute path, `..`, NUL, URL or archive syntax), except
   that a path returned by the provider in an earlier admitted receipt of this Task
   (e.g. a library source) may be used verbatim. Limits are bounded
   (`read_file.limit ≤ 400` lines; search `limit ≤ 50`; `includeExcluded` and
   `include_external` forced false in E1).
4. Model-supplied `projectPath` is rejected; lowering sets it from the Workspace root.

Denials append a `denied` journal entry and return a `PolicyDecision` observation;
nothing reaches the workstation.

**Lowered request** (retained artifact, then dispatched):

```json
{"version": 1, "kind": "WorkspaceOperationRequest", "payload": {
  "task_id": "task-…", "operation_id": "task-…/5", "workspace_id": "wsp-…",
  "workstation_id": "ws-…", "provider": "intellij-mcp",
  "mcp": {"method": "tools/call", "params": {"name": "search_text",
          "arguments": {"q": "customerStatus", "limit": 20, "includeExcluded": false,
                        "projectPath": "/home/alex/src/orchid-service"},
          "_meta": {"blaine/operation_id": "task-…/5"}}},
  "limits": {"max_response_bytes": 65536, "deadline_seconds": 30},
  "authority_ref": "artifact://…", "request_sha256": "…"}}
```

**Receipt** (admitted by the workflow as evidence):

```json
{"version": 1, "kind": "WorkspaceReadReceipt", "payload": {
  "task_id": "task-…", "operation_id": "task-…/5", "request_sha256": "…",
  "workspace_id": "wsp-…", "workstation_id": "ws-…", "session_id": "…",
  "provider": {"kind": "intellij-mcp", "ide_build": "262.10968.63"},
  "operation": "read_file", "state": "SUCCESS",
  "source": {"view": "ide_document", "class": "project",
             "path": "service/src/main/java/example/CustomerStatus.java", "lines": [40, 120]},
  "response_ref": "artifact://…", "response_sha256": "…",
  "response_bytes": 2311, "truncated": false,
  "dispatched_at": "…", "received_at": "…"}}
```

Provenance is explicit about what the IDE returned:

| Field | Values | Meaning |
| --- | --- | --- |
| `source.view` | `ide_document` (`read_file`), `ide_index_search` (search tools), `ide_tree` (`list_directory_tree`) | Which IDE view produced the bytes. `ide_document` may include unsaved edits; its digest is of the returned text, never a disk hash |
| `source.class` | `project`, `library`, `sdk` | Whether the file is project source or dependency/SDK source (from the provider path and its root); library and SDK content is read-only third-party context |
| `state` | Context Plane [result states](context-plane.md#6-result-and-fallback-semantics): `SUCCESS`, `EMPTY`, `DENIED`, `UNAVAILABLE`, `INVALID_CONTEXT`, `STALE`, `UNSUPPORTED`, `INSUFFICIENT_CONTEXT` | `EMPTY` is a valid search with no match, not proof of absence elsewhere; `UNAVAILABLE` covers no live route or delegation; provider errors such as a missing or binary file are `UNSUPPORTED`/`STALE` observations for cognition, not Task failures |

These receipts carry the Context Plane's workspace-target identity (workspace,
source path, returned-content digest and range), so the IntelliJ MCP provider can
serve as the remote implementation of the Context Plane's exact read and
lexical/symbol search semantics without a second workspace contract. Admission
checks Task, operation, request digest, workspace, workstation and current
session; the promise is one-shot, so a replay or a result for another
Task/operation is rejected (existing `submit_workspace_result` pattern, extended).

## Direct protocol extension

Minimal additions to the [direct transport](host-connection.md), negotiated as a
feature so E0.C peers keep working:

| Addition | Shape | Purpose |
| --- | --- | --- |
| Protocol version | Blaine protocol **3** adds `capability-relay/1` to the signed hello transcript, following E0.D's protocol-2 precedent | Explicit compatibility; protocol-1/2 clients keep working and simply have no workspace capability |
| Frame kind `5 Capability` | Same header (kind byte + 16-byte session ID), JSON payload ≤1 MiB | A logical channel separate from the ACP byte stream, so capability traffic can never reach IntelliJ's stdio |
| `DelegationObserved` (client → Hub) | Redacted MCP server descriptor from `session/new`, ACP `cwd`, IDE info | Hub builds the `DelegationSnapshot` |
| MCP JSON-RPC (both ways) | Standard MCP client messages (`initialize`, `tools/list`, `tools/call`, `ping`, notifications) | Hub MCP client ↔ IDE MCP server, via the bridge |

**Client bridge responsibilities** (protocol integrity only):

- At ACP `session/new`, take the IDE-supplied IntelliJ MCP entry out of the params
  forwarded to the Hub, keep its URL/token/stdio configuration locally, and send
  `DelegationObserved`. Other MCP entries (`use_custom_mcp`) stay unsupported and
  are reported, not forwarded.
- Open the local MCP transport the IDE specified, relay MCP JSON-RPC between the
  Capability channel and the IDE endpoint, enforce framing, size and deadline
  limits, JSON-RPC correlation, and MCP client-role method shape.
- Never originate a tool call, rewrite arguments or decide admissibility. Echo
  `_meta.blaine/operation_id` and the session ID in its relay envelope.
- Close the MCP transport when the ACP session ends; never retry a call on its own.

**Hub side:** the per-session `PersonalACP` process owns the MCP client for its
route and delivers admitted `WorkspaceOperationRequest`s (below). The kernel never
talks to a transport directly; it publishes requests and waits, as today.

## Delivery

The workflow retains the request, appends the `admitted` journal entry, sets the
existing `WorkspaceWait` (`input_type: workspace_result`) and suspends. Delivery is
by the live session route, not by the Task:

- While an ACP prompt turn that created or continues the Task is active,
  `PersonalACP` follows the Task (bounded inspect), dispatches each pending
  request for a workspace its route serves, and submits the receipt through
  `submit_workspace_result`. Progress is streamed to the chat.
- With no active route, the operation stays pending. A later session on the same
  workstation and workspace runs `continue <task-id>` (or the natural-language
  equivalent) to resume delivery. This matches the accepted Hub E1 flow
  ("inspect and explicitly continue the pending read").
- Automatic delivery to a live route without a user turn would build on E0.D's
  presence leases and ACP routing hook; it is a later extension, not an E1
  requirement.

No polling loop lives in conversation; the Restate wait is the durable state.

## Confinement

Under the delegated model the IDE's project model is the boundary; Blaine's job is
to not escalate beyond it.

| Concern | Handling |
| --- | --- |
| Root confinement, `..`, absolute paths | PolicyGate argument schema (workspace-relative only); IntelliJ additionally refuses paths outside project/library/SDK roots |
| Another open project | Delegated scope, but only reachable if Task relevance names its `workspace_id`; lowering pins `projectPath`, model cannot supply it |
| Another workstation with the same path | Different `workspace_id` and `workstation_id`; admission rejects receipts from the wrong route |
| Symlinks | IDE-defined: content the IDE treats as part of the project is in scope. Accepted residual; receipts record the provider-reported path |
| Special files, binary files | `read_file` returns only text documents; others become `UNSUPPORTED` receipts |
| Very large files / results | Line-windowed reads (≤400 lines), response cap 64 KiB, search limit ≤50; `truncated` recorded, never silently accepted as complete |
| Deleted / stale files | `STALE`/`UNSUPPORTED` receipt, or a later read with a different digest; both retained |
| Change during read | IDE returns a consistent document snapshot; evidence is that snapshot's digest and time, not a disk-state claim |
| Encoding | IDE document decoding; returned as UTF-8 text |
| Ignored / generated directories | Excluded content off (`includeExcluded=false`); not a security control, a relevance/size bound |
| Library / SDK sources | Readable through `read_file` (IDE boundary); only via paths the provider itself returned; labelled in receipts |
| Secrets inside project files | In delegated scope. Egress is governed by the Task's sharing/cloud policy: workspace content is `local-only` unless the Task permits otherwise |

## IDE context versus capability reads

| Input | Status | Evidence? |
| --- | --- | --- |
| Prompt text | User intent | No |
| `resource_link` (URI, name) | Relevance hint within delegated scope; a `file://` URI under a delegated project becomes a candidate path for the Task | No. Reading it is a `workspace.read` operation producing a receipt |
| Embedded resource content | Not advertised in E1 (`promptCapabilities.embeddedContext` stays false) | — |
| `workspace.read` receipt | Authoritative observation of what the IDE returned at that time, with provenance | Yes |

The existing unused-resource notice is replaced in E1 by: "Attached references
were used as hints; Blaine read them through the delegated workspace" when a
Task actually reads them.

## Disconnect and reconnect

| Situation | Task effect |
| --- | --- |
| IntelliJ closes, network loss, laptop sleep during a pending operation | Task stays `WAITING` (`workspace_result`); the blocking dependency shows the workspace, the E0.D presence of its workstation and "capability unavailable: no live route". Contract, journal and evidence unchanged. Nothing is cancelled |
| Reconnect, same workstation and workspace | New session; `continue` re-dispatches the **same** pending `operation_id` (reads are safe to repeat). First admitted receipt wins; late duplicates rejected |
| Reconnect with delegation off (`use_idea_mcp` disabled) or project not open | Still `WAITING`; the Task reports the smallest user action: enable delegation / open the project |
| Result arrives after response loss | Idempotent: same operation, one-shot admission |
| Provider error | Failure receipt; cognition continues. Not a Task failure |
| Registration retired, or the user states the workspace is gone | The user chooses: retarget (amendment), or cancel. No automatic failure or substitution |
| Turn budget, explicit cancel, human `fail` | `FAILED` / `CANCELLED` through existing lifecycle |

E1 has no automatic wait timeout; a suspended Restate wait costs nothing and is
visible. A Task never restarts because IntelliJ closed, and a human `WAITING` Task
is unaffected by any connection event.

## No-mutation evidence

The guarantee has three layers, in order of strength:

1. **Authority:** the READ_ONLY Task's effective authority contains no mutating
   operation class. PolicyGate cannot admit `apply_patch` or
   `execute_terminal_command` for it, even though the delegated surface offers them.
2. **Journal:** every admission and denial is in the hash-chained capability journal
   before dispatch. The `capability_journal` verifier deterministically checks that
   every `admitted` entry's class is `workspace.read`, that every `observed` entry
   has a matching admission, and that every entry references the READ_ONLY
   authority revision.
3. **Correlation:** every bridged MCP call carries a Blaine `operation_id`; the Hub
   MCP client only issues calls for admitted requests, so no unjournaled call path
   exists on the Hub.

What this proves: Blaine neither authorized nor invoked a workspace mutation. What
it cannot prove: that the user, the IDE, another agent or a compromised
workstation did not change files independently. Results state this limit.

## Completion Contract examples

Synthetic examples; organizations use neutral names. Full machine-readable
versions are in the [E1 design fixtures](../../experiments/personal-agent-hub/e1-design/contract-examples.json).
All three use task-type templates that contribute `no-mutation` and
`workspace-scope` automatically:

| Template criterion | Level | Verifier |
| --- | --- | --- |
| `no-mutation` — no mutating operation admitted or executed | REQUIRED, invariant | `capability_journal`: `operation_classes_subset ⊆ {workspace.read}` and `admitted_before_observed` |
| `workspace-scope` — every operation targeted the Task's workspace(s) | REQUIRED, invariant | `capability_journal`: `workspace_subset` |

### 1. Investigation — "Investigate why ExampleService returns 500 for this request."

Template `investigation@1`. Result artifact `findings` with schema
`InvestigationFindings@1`: `conclusion {status: supported|unresolved, statement}`,
`claims[] {text, citations[] {receipt_ref, path, lines, quote}}`,
`hypotheses[] {text, status: supported|refuted|open, citations}`, `uncertainties[]`.

| Criterion | Level | Verifier | Honest limit |
| --- | --- | --- | --- |
| `code-path-inspected` | REQUIRED | `evidence_citation`: ≥1 `read_file` receipt cited by a claim | Proves inspection happened, not that it was the right code |
| `findings-cited` | REQUIRED | `evidence_citation`: schema valid; every claim cites ≥1 admitted receipt; each `quote` appears in the cited receipt at the cited lines | Proves provenance, not correctness |
| `conclusion-explicit` | REQUIRED | `evidence_citation`: `conclusion.status` present; `unresolved` requires ≥1 `uncertainties` entry | Allows an honest "unresolved" completion |
| `cause-supported` | ADVISORY | `semantic_review`: evidence supports the cause without contradiction; low confidence → `unknown` | Model judgement; cannot override the deterministic rows |
| `user-accepts` (only if the user asked to confirm) | REQUIRED, `user` | `human_response`: accept / reject / investigate further | Human judgement |

Root-cause correctness is not mechanically provable here. The contract makes the
Task complete when the investigation is **evidenced and explicit about its
uncertainty**, and routes truth-judgement to advisory semantic review or the user.

### 2. Code understanding — "Explain how retry behavior works in this module."

Template `explanation@1`, result schema `ExplanationFindings@1` with
`topics[] {id, answer, citations, status: answered|not_found}`.

| Criterion | Level | Verifier |
| --- | --- | --- |
| `implementation-inspected` | REQUIRED | `evidence_citation`: ≥1 `read_file` receipt inside the module path |
| `topics-covered` | REQUIRED | `evidence_citation`: topics `trigger`, `limit`, `backoff` each present, `answered` with citations or `not_found` with the searches that failed |
| `claims-cited` | REQUIRED | `evidence_citation`: quote/line verification as above |
| `explanation-complete` | ADVISORY | `semantic_review`: no uncited behavior claims, no internal contradiction |

The required topics come from the user's wording ("retry behavior") via the
template's topic extraction, with `user` provenance. `not_found` is legitimate:
a module without backoff should say so with evidence of looking.

### 3. Locate implementation — "Find where customer status is computed."

Template `location@1`, result schema `LocationFindings@1` with
`candidates[] {path, lines, symbol, citations}`, `primary`, `ambiguity`.

| Criterion | Level | Verifier |
| --- | --- | --- |
| `search-performed` | REQUIRED | `capability_journal`: ≥1 observed `search_*` operation |
| `location-evidenced` | REQUIRED | `evidence_citation`: each candidate cites a `read_file` receipt whose returned lines contain the cited span |
| `ambiguity-reported` | REQUIRED | `evidence_citation`: `primary` set with one candidate, or `ambiguity` non-empty when ≥2 candidates or none |
| `call-path-attached` | ADVISORY | `evidence_citation`: primary candidate has ≥1 caller citation (search or read) |

Deterministic checks catch fabricated locations: a cited line span that is absent
from the admitted receipt fails `location-evidenced`.

## E1 acceptance

Every run retains client/IDE/AI Assistant/transport/server versions, the redacted
`session/new` MCP descriptor, `DelegationSnapshot`, authoritative Task snapshots,
contract, journal, receipts and evaluations. No live tests were run by this design.

**Positive (live, second workstation, disposable synthetic project):**

1. `blaine integration jetbrains install` registers Blaine and sets its per-agent
   `use_idea_mcp`; `check` reports delegation configured and other agents' MCP
   settings unchanged. No Blaine approval step exists. The Hub records a
   `DelegationSnapshot` containing mutating tools, without the IDE token.
2. `access = read_only` is selected through configOptions and compiled into the
   Task's `EffectiveAuthority`.
3. An investigation Task (example 1) runs search and read operations through the
   bridge; receipts are admitted to the **same** Task; contract evaluates
   `satisfied`; `TaskResult.completion_ref` explains why from artifacts alone.
4. The journal shows zero admitted non-`workspace.read` operations, and the
   `capability_journal` verifier independently confirms it.
5. Disconnect (quit IntelliJ) while an operation is pending → `WAITING`
   (capability unavailable); reconnect, `continue`, same Task, same `operation_id`,
   completion. A separate human-`WAITING` Task is untouched.
6. Hub process and Restate restart while pending → same contract, journal and wait.

**Negative (deterministic; fixture MCP server that counts calls, plus live where noted):**

| Case | Expected |
| --- | --- |
| Scripted cognition proposes `apply_patch`, `create_new_file`, `execute_terminal_command` | PolicyGate `denied` journal entries; **zero** calls reach the IDE fixture; Task continues |
| Unclassified/unknown tool | Denied |
| Model supplies `projectPath` or targets a workspace not in authority | Denied |
| Absolute path, `..`, URL, `jar://` argument | Denied by argument schema |
| Receipt from another workstation, stale session, other Task, replayed operation | Rejected; one-shot admission holds |
| Findings cite a quote not present in the cited receipt | `findings-cited` `failed`; no COMPLETED |
| Cognition attempts to drop or downgrade a REQUIRED criterion | Rejected; only a human amendment can |
| Synthetic journal with an `observed` entry lacking admission | `no-mutation` `failed` |
| Delegation absent (`use_idea_mcp` off) | Operations wait with an actionable blocker; no fallback provider |
| Oversized result | Truncated receipt recorded as such; never counted as full evidence |

**STOP:** IntelliJ does not pass its MCP server to a custom ACP agent; the passed
surface lacks read/search tools; the bridge cannot correlate calls to operations;
a result is accepted into the wrong Task; a Hub checkout or host filesystem read is
needed; or no-mutation cannot be shown from the journal.

## Extension to E2 and E3

E1 adds nothing dormant for writes, and E2 needs no new provider integration: the
same delegated IntelliJ MCP surface, bridge and journal serve both. Moving from E1
to E2 changes the Task's effective authority (operator policy may allow write or
execute classes), not the provider. E2 extends by composition:

| E2 need | Extension point |
| --- | --- |
| Conditional writes, patches | Classify the already-delegated `apply_patch`/`create_new_file` as `workspace.write`; new configOption value; PolicyGate argument schemas with expected-hash preconditions |
| Uncertain effects | Journal `admitted` entry already precedes dispatch; E2 adds `uncertain` reconciliation before any redispatch (reads may repeat, writes may not) |
| Bounded execution | Classify `execute_run_configuration` (reviewed profiles) as `workspace.exec`; `capability_result` verifier on exit code and test report |
| Scope of change | `change_set` verifier over admitted diffs |
| Approvals | User constraint `edit_with_approval` → `autonomy.ask_before` → existing `human.request` wait |

The E2.A provider questions in the Hub design remain open (IntelliJ MCP write
tools confine lexically and offer no compare-and-swap). E3 composes Completion
Contract + E1 reads + E2 effects + human wait/resume + verification + memory
suggestions without changing any E1 contract.

## Accepted residuals and remaining gates

- **Compromised Hub** — accepted for the current threat model; see the
  [security model](#security-model) and ADR 0027.
- **Editor state.** `read_file` evidence may reflect unsaved edits. E1 labels it;
  E2 must decide dirty-buffer reconciliation before disk-based verification.
- **E1.A live gate.** The installed IDE's real delegation shape is not inferred
  from documentation: E1.A records a redacted `session/new` (MCP endpoint form and
  session metadata, how `use_idea_mcp` manifests, project identity/path
  representation, exposed tool list, per-agent config key) and demonstrates that
  the MCP auth token stays on the workstation and in no artifact, log or commit.

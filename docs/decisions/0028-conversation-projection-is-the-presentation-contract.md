# ADR 0028 — The conversation projection is the presentation contract

**Status:** Accepted  
**Validation:** Unvalidated

## Context

PA-3 proved real coding delegation end to end, but its desktop client assembled the product
state itself: it polled raw `inspect`/`events` per Task, derived lifecycle rows, completion
progress and pending human requests in TypeScript, and projected delivery by reading raw
Conversation messages. `personal_acp` (IntelliJ) used none of the PA-3 services, so the same
delegation would look different — or not exist — per client. Every client re-deriving
product semantics from diagnostics APIs guarantees drift.

## Decision

The Personal Agent backend exposes one **conversation projection** per Conversation
([contract](../contracts/conversation-projection.md)): ordered entries (messages, briefs,
Tasks, human requests, results, follow-ups) with a durable monotonic cursor. It is built only
from the Conversation store and the Task control surface, is read-only and derived, and never
owns lifecycle, authority or completion.

- Clients render the projection; they do not derive Task semantics from raw APIs.
- `personal_acp` and the desktop consume the same projection.
- Raw `inspect`/`events`/`artifact` remain diagnostics.
- Transport starts as cursor polling; push is a later transport change.

## Consequences

Presentation semantics live in one tested Python module; clients shrink. New clients (Telegram,
mobile) get the same semantics for free. The projection adds per-read `inspect` calls for
non-terminal Tasks and a small digest table. Push delivery, multi-Conversation feeds and
non-delegated Tasks are deferred.

## Validation

### Hypothesis

One projection can drive both the desktop and ACP renderings of the same delegation without
client-side derivation, with loss-free reconnect.

### Validation level

Integration (projection + both adapters against the live bridge/runtime).

### Minimal validation

Deterministic tests of cursor/idempotency/ordering and of the ACP mapping; one live delegation
rendered from the projection in the desktop and followed from an ACP session attached to the
same Conversation.

### Evidence

Both clients show the same Task phase, steps, pending request and result from the same
entries; a reconnect with the old cursor resumes without loss or duplication; the desktop no
longer calls `inspect`/`events` for presentation.

### Not required for validation

SSE/WebSocket, multi-Conversation views, IntelliJ plugin changes, Memory.

## Reconsider when

Push transport is needed for latency, or entry bodies become too costly to recompute on read.

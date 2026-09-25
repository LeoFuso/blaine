# CP.2 executable subset — governed declared/observed Memory writes

**Implementation candidate; CP.2 PARTIAL.** Deterministic enforcement passes; native
MIRIX commit/embedding/restart acceptance is pending trusted HOST suite publication.
This document does not claim storage acceptance or authorize deployment. See
[milestone 056](../milestones/056-context-plane-cp2-storage-qualification.md) and
[qualification evidence](../../experiments/context-plane-cp2/evidence/implementation/qualification.json).
The [Context Plane semantic contract](context-plane.md) remains authoritative.

## Authority and entry points

`PersistentMemoryFacade` is an opt-in replacement for the CP.1 read facade. The
trusted application injects the existing `LocalContextAuthority`, storage adapter,
and a private `MemoryWriteGrant` provider. No default deployment is changed.

`memory.recordObservation` is a Cognitive Loop capability, admitted by PolicyGate
and recorded by the existing admission/observation journal as `memory.write /
TARGET_EFFECT`. It requires capability/autonomy authority, an active Context Plane,
and a freshly resolved write grant. A no-mutation contract does not treat it as a
read. Its only input fields are `content` and `idempotency_key`.

`PersistentMemoryFacade.declare` is a separate trusted operator application API,
requiring an explicit `declare` grant and intent to remember. There is no worker
capability or new public HTTP route for this method. To declare at a parent, the
operator must obtain a direct trusted binding/grant to that context; it is not a
copy or promotion from a child.

Both paths require a RUNNING Task, matching Task/spec/principal/binding fingerprint,
the **current** context, an eligible security domain and an explicit local-processing
grant. Caller payloads cannot supply origin, verification, retention, authority,
context, security domain, backend, record ID or operation class. Each retry resolves
current authority; a serialized reference is never a grant.

| Trusted entry point | Provenance (`origin`) | Verification (`status`) | Retention |
|---|---|---|---|
| Agent observation | AGENT_OBSERVATION | UNVERIFIED | WORKING |
| Explicit operator declaration | USER_DECLARATION | DECLARED | RETAINED |

There is no transition API. A later explicit declaration creates a distinct entry;
it cannot upgrade an earlier observation in place. Source text is limited to 4,096
UTF-8 bytes and the retry token to 80 characters. Runtime assigns creator, source
Task identity, context/domain references, content digest and schema version.

## Existing MIRIX substrate and transaction

`MirixProcessStore` uses a fixed child-process bridge to the existing MIRIX Python
environment; no additional service or worker backend tool is introduced.
`PostgresMirixStore` stores exact source text and a local embedding in MIRIX's
existing `raw_memory` table. The metadata-only `blaine_memory_entry_v1` registry
lives in the **same approved PostgreSQL database**, not a second Memory product.
It owns scoped retry identity and immutable Blaine metadata; source content is not
duplicated there. Organization/user/client identities are deployment-held and must
already exist. The namespace is a private, stable deployment identity.

Explicit schema installation is idempotent and separate from reads/writes. No
existing raw row is reclassified or backfilled. Version-1 registry metadata includes
context/domain, origin/status/retention, creator, source Task identity and digest.
A restrictive foreign key prevents MIRIX's age-only raw cleanup from silently
discarding either admitted class. This is a guard against ungoverned deletion, not
a WORKING-to-RETAINED transition. CP.2 adds no TTL, automatic cleanup or retention
scoring. Native migration/cleanup-guard qualification remains pending.
An age-cleanup transaction touching an admitted row can consequently fail; CP.2
does not claim all legacy cleanup continues unaffected. Broader governed removal
and retention lifecycle design remains deferred.

One transaction commits source, vector, metadata and retry identity. Scope-specific
serialization and a unique identity use namespace/context/domain plus a hash of the
write kind and caller retry token; WORKING additionally includes source Task identity.
Same identity and payload replays; changed payload conflicts. New context/domain
identities cannot collide with or disclose foreign entries. UUID row IDs are generated
by the adapter, never selected by a caller.

The only admitted processing route is the existing loopback embedding service
(`BAAI/bge-m3`, 1,024 dimensions padded to MIRIX's 4,096-column representation).
Provider redirects/proxies and alternate endpoints/models are refused. Vector and
source share the same scoped row; neither embedding nor persistence changes metadata.
No vector search, extraction, consolidation, auto-dream or remote provider is enabled.
This qualifies a narrow adapter, not every MIRIX API, cache or processing pipeline.

## Receipts, reads and compiled context

A backend return alone is insufficient. The facade re-resolves trusted authority and
retrieves through its canonical read method before returning `RECORDED`. The receipt
contains identity, provenance/status/retention and CREATED/REPLAY, without source text
or evidence artifacts. A lost response gets one read-only identity lookup; it never
causes blind redispatch. A still-unknown effect or post-commit readback/revocation
failure returns uncertainty. The existing E1 legality check blocks completion with
an unresolved uncertain Memory effect. Durable work owns any later retry.

Reads intersect permitted ancestry, SecurityContext and policy **before** loading
records or applying limits. WORKING is visible only in its current context and source
Task, including reconstruction of that Task. It is not reusable by another Task in
the same context or inherited by descendants. RETAINED can be inherited through
permitted ancestors. Parents, siblings and unrelated security domains receive no
implicit access. Missing and forbidden by-ID reads share DENIED behavior.

The facade validates metadata tuples, digests and scope again after storage readback.
Malformed data fails closed. Reads are lexical/exact, bounded to 32 entries; overflow
returns UNAVAILABLE rather than an unbounded result. CP.1's distinct Resolver and
Compiler consume these candidates through the existing interface. Fresh resolution
can see a new permitted entry; no write automatically injects every entry into prompts.
Worker packets preserve origin/status/retention and derived-knowledge uncertainty,
omit backend/private scope metadata, and retain the existing explicit packet budget.

Task constraints and the current revisioned Completion Contract remain authoritative.
The roadmap explicitly defers preference precedence: CP.2 exposes source classes and
conflicts without inventing a human-preference override or upgrading observations.
Even exact matching Memory text is not completion evidence.

## Qualification and limits

`tests/test_kernel_memory_writes.py` exercises the production facade/capability,
compiler and Cognitive Loop with an explicitly identified storage test double.
It proves admission, forgery denial, hierarchy/domain isolation, scoped retry,
unknown-effect legality, bounded delta delivery and journal replay. It does **not**
prove native persistence.

The additive `context-plane-memory-native` HOST suite executes the fixed
`experiments/context-plane-cp2/accept_native.py` against the submitted checkout.
Only reviewed suite/probe definitions are independently published as trusted
verification infrastructure; candidate Python is never imported into the scheduler.
The harness uses existing services, synthetic scoped records, post-commit writer
SIGKILL, facade readback, a restart of **only `blaine-mirix.service`**, fresh bindings
and compiled delta checks. It explicitly removes its synthetic records afterward.
It does not reboot the host, restart PostgreSQL/Restate, or provision infrastructure.

CP.2 cannot PASS until that canonical HOST run proves both retention classes, local
embeddings, scoped idempotency, committed facade readback and restart isolation.
CP.3, verified learning, reflection, promotion, declassification, semantic workspace
retrieval, Graphify and Conversation-to-Memory ingestion remain out of scope.

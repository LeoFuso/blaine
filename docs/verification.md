# Local Verification Architecture

Blaine now has multiple concurrent development worktrees and agents. Each
increment needs local qualification: pytest/unit/contract tests, native Restate
integration, Goose, PostgreSQL or other host services, and eventually
vLLM/GPU, remote peers, and domain-specific scripts.

This document defines the local verification system for exactly that, built
around one core principle:

> **verify, don't provision.**

Verification tooling *observes* the host and *runs existing* qualification.
It never installs Restate, Goose, PostgreSQL or vLLM; never configures a GPU;
never fetches secrets; never mutates long-lived host configuration; and never
bootstraps the Blaine machine. A missing prerequisite is **BLOCKED**, never a
PASS and never a silent provision.

---

## The three layers

| Layer | Tool | Role |
|-------|------|------|
| Assertions | **pytest** | Test semantics: discovery, fixtures, assertions, parametrization. Reused, never reimplemented. |
| Named workflows | **nox** | Thin orchestration: named local verification workflows that invoke the authoritative commands. |
| Durable scheduling | **Restate** | Durable scheduler + host-resource arbiter for **HOST**-bound qualification. |

Blaine-specific code provides only:

- suite metadata and additive discovery;
- prerequisite probes (observe, never provision);
- durable scheduling and host-resource coordination;
- result normalization into PASS / FAIL / BLOCKED;
- machine-readable evidence/reporting.

It does **not** provide a test framework, a remote shell, or a second scheduler.

---

## Verification classes

Every suite declares how much of the Blaine host it needs.

| Class | Meaning | v0 |
|-------|---------|----|
| **HERMETIC** | Runs from a normal checkout/worktree with no pre-existing Blaine host services. | Fully executed. |
| **HOST** | Requires services/resources already configured on the canonical Blaine host (Restate, Goose, PostgreSQL, ...). | Fully executed via the Restate scheduler. |
| **FLEET** | Requires another host/device/peer. | Representable, deferred. |
| **CI_ONLY** | Semantics specific to GitHub CI / release infrastructure. | Representable, deferred. |

v0 fully executes HERMETIC and HOST. FLEET and CI_ONLY are representable but
deferred. Unavailable environments are never faked: a suite whose class it
cannot satisfy reports BLOCKED.

---

## Result semantics

Qualification results normalize to exactly three values.

| Result | Meaning |
|--------|---------|
| **PASS** | Verification executed and satisfied its assertions. |
| **FAIL** | Verification executed and demonstrated incorrect behavior. |
| **BLOCKED** | Verification could not validly execute because a required prerequisite or resource was unavailable. |

A missing Restate / Goose / service / peer is **BLOCKED**, never **PASS** and
never confused with **FAIL**. The distinction between "the code is wrong" and
"the thing we need is not here" is load-bearing.

---

## Verify, don't provision (rule)

Verification tooling **may**:

- detect installed tools and their versions;
- detect service health;
- inspect the worktree/commit;
- acquire scheduler permission;
- execute existing tests and native smokes;
- produce reports.

It **must not**:

- install Restate / Goose / vLLM;
- provision PostgreSQL or configure a GPU;
- configure remote peers;
- fetch secrets;
- mutate long-lived host configuration;
- automatically bootstrap the Blaine machine.

Concretely: `Restate required but unavailable` → `BLOCKED: RESTATE_UNAVAILABLE`,
not "install a new Restate environment". If an existing accepted command merely
starts an already-configured, test-local process as part of its suite, that is
preserved (it is the suite's own behavior), but provisioning new infrastructure
is forbidden.

---

## Strict FIFO v0 + one active host run

For v0 the host-bound queue uses a **strict FIFO** policy with the conservative
rule:

> **At most ONE host-bound qualification run is active on the canonical Blaine host at a time.**

This is intentionally slower than concurrent execution. It buys:

- deterministic ordering;
- no host-resource deadlock;
- no accidental Restate / Goose cross-worktree interference;
- FIFO fairness for admitted queued runs.

**Atomic resource principle.** A run never acquires one host resource and waits
while holding it for another. Resource requirements belong to the *run as a
set*; admission is atomic. With at most one active host run and no partial
acquisition, **multi-resource deadlock is impossible by construction**.

**FIFO fairness claim (precise).** FIFO ordering holds for *admitted queued
runs* under the assumptions that running suites terminate or time out and the
scheduler itself remains available. This system does **not** claim unlimited
starvation freedom across a system outage, infinite retries, or a future
priority scheme.

**Timeouts / interruption.** A bounded interruption window releases the active
slot, so an interrupted or hung run never permanently starves later queued work.

---

## Restate role

The smallest durable scheduler, `VerificationScheduler[host="blaine"]`, owns:

- the queued host runs (FIFO),
- the active host run,
- ordering / admission,
- lifecycle transition coordination.

Each execution has a durable identity, `VerificationRun[run_id]`. The in-process
core (`verification/scheduler.py`) implements the queue policy and lifecycle
*semantics* once; the Restate object (`verification/scheduler_restate.py`)
wraps them so durable execution, admission, and release live in Restate while
the decision logic is written once. No Quartz. No second scheduler.

### Host run lifecycle

```
SUBMITTED -> QUEUED -> PREFLIGHT -> RUNNING -> COLLECTING_RESULT -> PASS | FAIL | BLOCKED
                                                    ^
                                            (bounded interruption)
                                            -> INTERRUPTED -> slot released
```

The scheduler releases its active slot after every terminal state.

### SDK notes (protocol v6)

- `ObjectContext.set` / `WorkflowContext.set` are **synchronous**; do not `await` them.
- `ctx.get(name, type_hint=list)` — the second positional argument is a serde, not a bare type; use `type_hint=` for non-default types.
- `ctx.object_call` / `workflow_send` require a **registered handler reference**, not a plain module function.
- In protocol v6, **Workflow → VirtualObject `object_call` is unreliable** (silently dropped); **VirtualObject → Workflow `object_call` works**. The v0 topology uses only VO→WF, with the scheduler's shared `_full_dispatch` doing admission → blocking call to the run → release → recurse.

---

## Worktree safety

Multiple Git worktrees may run verification concurrently.

- Never assume `/home/leofuso/workspace/blaine` is the checkout being tested.
- All checkout-local operations resolve the **actual** target worktree via Git
  (`rev-parse --show-toplevel`, `branch --show-current`, `rev-parse HEAD`,
  `status --porcelain`).
- Mutable coordination state is **not** stored inside one worktree.
- Reports record the **tested worktree root, branch, commit, and dirty state**.
- A suite tests the code belonging to the requested worktree.

---

## No central edit hotspot (additive discovery)

A major goal is reducing cross-worktree merge conflicts. **Adding a suite means
adding a file** — it does not mean editing a giant central list, manifest, or
shell script.

```
verification/
  suites/
    sample_hermetic.py          # SUITE = Suite(...)  -> "sample-hermetic"
    completion_contract.py      # SUITE = Suite(...)  -> "completion-contract"
    completion_contract_native.py
    future_context_plane.py     # added additively after CP.1 merges
    future_remote_execution.py
```

A module is a suite iff it exposes a top-level `SUITE` object. The suite name
must match the file stem. Discovery scans `verification/suites/`; no central
registry is edited. Nox sessions (`hermetic`, `pre_handoff`) pick up new
suites automatically.

---

## Resource declarations

Each suite conceptually declares the host resources it uses, so later
concurrency can be introduced without changing suite semantics:

```python
SUITE = Suite(
    name='completion-contract-native',
    verification_class=VerificationClass.HOST,
    steps=[...],
    resources=('restate-runtime',),   # conceptual; v0 admits the whole set atomically
    prereq_probes=('restate',),       # probes that gate execution
)
```

v0 does not implement generalized capacity scheduling; the resource list is
metadata that admission and reporting use.

---

## Prerequisite probes

Probes observe only. The first host-bound suite (completion-contract-native)
requires the Restate toolchain, so exactly one probe is implemented:

- `restate` — checks the `restate-server` binary and the runtime venv python,
  and that `restate-server --version` answers with a semver.

Probe results are one of **AVAILABLE / UNAVAILABLE / MALFORMED**. UNAVAILABLE
and MALFORMED both feed **BLOCKED** (a missing tool and a surprise-shaped tool
are never a PASS). Do not add speculative probes for subsystems no current
suite needs.

---

## Report / evidence format

Reports are portable JSON (schema v1). A report records, at minimum:

- `run_id`, `suite`, `result` (PASS/FAIL/BLOCKED), `reason`;
- `worktree`: root, branch, commit, dirty;
- `verification_class`, declared `resources`, `prerequisites` (probe results);
- `steps`: executed commands, child exit codes, stdout/stderr tails, durations;
- `timing` (admitted/started/completed, duration);
- `environment`: python version, OS, hostname.

Reports never record secrets or raw proprietary context.

**Location.** Ordinary runs write to a worktree-safe, Git-ignored local
location: `<worktree>/.local/verification/runs/<run_id>/report.json`
(`.local/` is already in `.gitignore`). Reports are unique per run_id, so
concurrent worktrees never overwrite each other. Milestone / handoff evidence is
promoted **explicitly** via `verification.report.promote(...)`; it is never
auto-committed.

---

## How to add a new suite

1. Create `verification/suites/<name>.py` (kebab-case name = file stem with
   underscores).
2. Define a top-level `SUITE`:

   ```python
   from verification.suite import Step, Suite, VerificationClass

   SUITE = Suite(
       name='future-context-plane',
       verification_class=VerificationClass.HERMETIC,   # or HOST
       description='Context Plane qualification.',
       steps=[
           Step(name='cp-unit',
                command=['BLAINE_PYTHON', '-m', 'pytest', 'tests/test_context_plane.py', '-q'],
                env={'BLAINE_PYTHON': ''}),
       ],
       resources=(),            # conceptual host resources (HOST suites)
       prereq_probes=(),        # probe names that gate the run
   )
   ```

3. Use `BLAINE_*` placeholders for toolchain values; the executor substitutes
   them from the resolved environment. Whole-argument placeholders only
   (`$NAME` or bare `NAME` where `NAME` is an env key and looks like an
   identifier).
4. Done. No central file, nox session, or registry is edited. `list` and the
   `hermetic` / `pre_handoff` sessions see it automatically.

For a **HOST** suite, declare `resources` and `prereq_probes`, and add a probe
to `verification/probes.py` only if the suite actually needs one (observe, never
provision).

---

## How Context Plane verification is added after CP.1 merge

CP.1 is being reconciled in its own worktree and is **not** yet merged into
main. Context Plane verification must **not** be implemented now and must **not**
copy the CP.1 implementation from another worktree.

After CP.1 merges:

1. Add `verification/suites/context_plane.py` with a `SUITE` whose steps invoke
   CP.1's *existing* authoritative tests/scripts (by name), exactly like
   `completion_contract.py` does.
2. If CP.1 qualification is host-bound, declare `resources` and the matching
   `prereq_probes` (e.g. `restate`), so it queues behind the single active host
   run rather than running concurrently with another host suite.
3. Register any genuinely new probe in `verification/probes.py` if a new
   prerequisite is required.
4. No central registry, nox session, or production change is needed.

The discovery model is already shaped so this is purely additive.

---

## Canonical usage

**List suites** (additive, no central registry):

```
<python> -m verification.cli list
```

**Run a HERMETIC suite directly** (no host services, no Restate queue):

```
<python> -m verification.cli run <suite> --worktree <git-worktree-path>
```

**Run the E1.0 Completion Contract qualification:**

```
<python> -m verification.cli run completion-contract
```

**Run the deterministic scheduler unit tests:**

```
<python> -m pytest verification/tests.py -q
```

**Named workflows (nox):**

```
BLAINE_PYTHON=<venv-python> nox -s hermetic             # every HERMETIC suite
BLAINE_PYTHON=<venv-python> nox -s completion_contract   # E1.0 contract
BLAINE_PYTHON=<venv-python> nox -s scheduler             # scheduler unit tests
BLAINE_PYTHON=<venv-python> nox -s pre_handoff           # canonical pre-handoff
```

**Submit a HOST suite to the Restate scheduler** (v0): the Restate
`VerificationScheduler[host]` ingress accepts `submit` with a *named* suite and
a worktree. `submit(command=...)` does not exist — the commands always come from
the repository-owned suite definition. The bounded native acceptance harness is:

```
<python> verification/accept_native.py --restate-server <bin> --python <py> \
    --output <fresh-scratch-dir> --evidence <dir>
```

### The future handoff pattern

Prompts should say:

> Run the repository's canonical pre-handoff verification for the relevant
> subsystem.

— not embed a static list of test commands. The canonical entry is the
`pre_handoff` nox session (hermetic layers) plus a Restate submission for the
host-bound suites, discovered from the repository, not from a stale prompt.

---

## GitHub CI

This system does **not** attempt to make the canonical Blaine host
reproducible from scratch, and does **not** modify GitHub Actions to run host
suites in GitHub. The architecture simply allows later GitHub Actions to invoke
the **HERMETIC** nox sessions. HOST qualification remains local on the
configured Blaine environment for now. The distinction is: HERMETIC = CI-able;
HOST = local-only (v0).

---

## Future: shared local resource arbitration

The Verification Scheduler v0 is the **first production consumer** of a broader
resource-claim pattern, but it remains verification-specific by design. The
generic direction is recorded here as **FUTURE**; nothing in this increment
generalizes the implementation.

> **Generalize the contract, not the implementation.**

The pattern already present in v0 — a *named run declares a set of resources as
data*, a *trusted durable arbiter admits the whole set atomically or not at
all*, and *workers never coordinate shared resources ad hoc* — is the contract
future consumers would share. v0 keeps that contract but does not yet expose it
as a generic `ResourceScheduler`.

### What is generic enough today (contract only)

- A run declares **resource claims as data** (`Suite.resources`), not
  hard-coded scheduler logic.
- Admission is **atomic**: the whole declared set is granted together, or the
  run stays queued/blocked. No partial acquisition.
- **Admission/release ownership is centralized** in the durable scheduler; a run
  never grants or releases resources itself.
- **Terminal failure/cancellation releases the slot**, so one bad run cannot
  permanently retain a resource.
- **Worktree identity is observed from Git**, not stored as coordination state.
- **Restate is the durable coordination owner**; there is no second scheduler.

These properties mean v0 does not *prevent* future generalization. They do not
*provide* it.

### What remains deliberately verification-specific

- The strict FIFO, at-most-one-active-HOST-run policy is verification's choice,
  not a generic scheduling policy.
- The `restate` prerequisite probe and the E1.0 suite are verification concerns.
- PASS / FAIL / BLOCKED semantics are qualification semantics, not generic
  resource-outcome semantics.

### What is explicitly FUTURE (not implemented)

A future trusted durable arbiter may admit claims with identities such as:

```
workspace:<canonical-id>
gpu:<device>
service:<name>
port:<number>
verification-host
```

and claim modes such as:

```
shared read
exclusive write
capacity / count based
```

These are **not implemented**. Future consumers must prove their requirements
before the scheduler is generalized. There is no generic workspace lease
manager, no read/write workspace modes, no GPU capacity allocation, and no
priorities/aging/generalized capacities in v0.

> **Resource coordination is trusted infrastructure surrounding Tasks. It is not
> Worker-owned authority.**

A Worker may *request* resources. A Worker must not *grant itself* resources or
bypass arbitration.

### Workspace direction (FUTURE, not implemented)

For coding agents, a workspace/repository is likely to become a **first-class
shared resource**. A future Task is expected to have an *externally granted*
workspace scope:

```
Task authority     permits repository/workspace
Task / Worker      requests workspace claim
resource arbiter   admits claim
Worker             receives usable checkout/worktree
```

Possible future behaviors (not decided here):

- read-only Task → shared workspace/read claim;
- writing Task → exclusive workspace/write claim;
- writing Tasks → isolated Git worktrees.

**This policy is intentionally not frozen in this increment.** PA-3 real coding
delegation should produce evidence (real workspace contention) before the
workspace-claim mode is decided.

### Relationship to future PA-3 (coding delegation)

One integration expectation, recorded now and **not implemented**:

> Coding Workers may perform bounded local development work, but host-bound
> canonical qualification should use the **Local Verification Scheduler** rather
> than inventing another host-verification coordination mechanism.

PA-3 will consume the merged scheduler later; it will not build a second host
verification coordinator.

---

## Out of scope (v0)

- Production Blaine Cognitive Loop semantics (unchanged).
- Completion Contract behavior (reused as-is; only exposed cleanly).
- The CP.1 worktree (untouched).
- Context Plane verification before it merges.
- Remote-machine / FLEET execution.
- GitHub self-hosted runner.
- Full host bootstrap.
- Quartz, generalized distributed locks, parallel resource-capacity scheduling,
  priorities, priority aging, GPU scheduling.
- Production deployment.
- Cloud model invocation.

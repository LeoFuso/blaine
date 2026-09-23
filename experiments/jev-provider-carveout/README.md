# Isolated TypeSafe/Jev provider candidate

Jev is **not adopted**. This slice finishes the provider integration against
boundaries Blaine already owns, so the later comparison in
[roadmap C3](../../docs/roadmap/001-blaine-development-roadmap.md) can be run on
evidence rather than on a fresh one-off script.

Nothing here changes routing. The accepted `ScriptedClassifier` still decides,
the kernel contains no reference to this provider, and an offline control asserts
that. Qwen, Codex and Claude routing defaults are untouched, no E0 client or
workstation code is involved, and no Task-level OpenTelemetry work is included.

## What it plugs into

| Existing boundary | Where it is defined | What the candidate supplies |
| --- | --- | --- |
| `WorkloadClassifier.assess` | `runtime/kernel/worker_routing.py` | A suitability judgement in the existing `UNDERPOWERED` / `JUST_RIGHT` / `OVERKILL` vocabulary |
| `BoundaryObserver.inspect` | `runtime/kernel/instrument.py` | A closed `PROCEED` / `ABSTAIN` assessment carrying a label, confidence, latency and token counts |
| Observed usage | `runtime.kernel.frontier.validate_usage` | `model_calls`, `input_tokens`, `output_tokens`, with cost left UNKNOWN |

No new vocabulary was introduced. The provider is asked the same question the
accepted classifier answers, so its output drops into the existing `Assessment`
without translation, and `select()` still applies Blaine's separate hard gate.

Expected cost-to-success ranks remain explicit scripted deployment inputs. The
provider is never asked to invent prices it cannot observe, and the SDK exposes
no cost field, so monetary cost stays UNKNOWN rather than estimated.

## Shadow mode keeps it a candidate

`ShadowClassifier` runs the accepted classifier for the decision and the candidate
only for observation. The returned assessment is always the accepted one, so no
routing outcome can change while Jev is unadopted. Disagreements, agreement and
bounded provider failures are recorded for the comparison and never applied. A
candidate that fails, times out or returns an answer outside the vocabulary
leaves routing untouched.

At the continuation boundary the same rule holds in the stronger form the
[boundary contract](../../docs/contracts/worker-execution-boundary.md) already
requires: the classification becomes a label, the outcome stays `PROCEED` or
`ABSTAIN`, and an unavailable provider abstains instead of blocking execution.

## Credential handling

The credential is `TYPESAFE_API_KEY`, the SDK's own variable. It is managed in
Bitwarden Secrets Manager and delivered by the
[secret-delivery standard](../../docs/platform-secrets.md): an operator
materializes it once into a local `0600` consumer credential, and the provider
reads only that. This integration has **no** Bitwarden or keyring knowledge — it
checks whether the variable is present and lets the SDK read it, never binding,
copying, logging or retaining the value. Provider diagnostic text is discarded
and replaced by a closed failure category, because a provider message can quote
submitted state back into evidence. Offline controls assert that no credential
and no provider text reaches a result or a failure.

## Running the authenticated call

The probe makes **exactly one** provider call by default, classifying a synthetic
binding through the routing seam. It consumes no frontier dispatch grant, runs
outside Task lifecycle and changes no default.

```sh
python3 infra/secrets.py materialize jev          # operator, once, and on rotation
python3 infra/secrets.py run jev -- python3 \
    experiments/jev-provider-carveout/probe_jev.py \
    --output experiments/jev-provider-carveout/evidence/live
```

`--include-boundary` adds one further call exercising the continuation-boundary
observer. Without a credential or without the optional SDK the probe reports
`BLOCKED` and makes no call, as [preflight.json](evidence/preflight.json) shows.

[Live evidence](evidence/live/summary.json) records the authenticated result:
model identity, latency, token usage, the returned classification and its
confidence, with cost UNKNOWN because the provider exposes no cost field.

Offline controls need neither the credential nor the SDK:

```sh
PYTHONPATH=.:tests python3 -m unittest discover -s tests -p 'test_jev_provider.py'
```

## Self-disabling, and what it cannot do

`CandidateBreaker` stops consulting the candidate once the provider starts
refusing: after a threshold of consecutive refusals it opens, no further calls
are made, the accepted classifier keeps deciding, and one warning is emitted.
Comparison rows keep accumulating with `circuit_open_<state>` so the gap stays
visible rather than silently disappearing.

Nothing is declared in advance, because **the provider publishes no balance**. A
live probe observed only `x-typesafe-request-id` and generic CDN headers — no
credit, quota or remaining-limit header — and the SDK models only `retry-after`
and 429. There is also no `402` in its status map, so an exhausted account is
indistinguishable by status code from a revoked key or a denied account; the
breaker treats all refusals alike for that reason.

| Property | Behaviour |
| --- | --- |
| Protects against | Wasted calls and repeated failures *after* refusals begin |
| **Does not** protect against | Spending the final credit; exhaustion is only visible once the provider refuses |
| Warning before exhaustion | **Impossible** without a published balance or an operator-declared budget |
| Inconclusive failures | Denied as `unknown`, by the existing rule that an unobservable ceiling is never a permission |
| Recovery | An explicit operator `reset()` after topping up; no automatic retry, which would burn more calls |

State is expressed through the existing `GlobalGuardrails` contract, so
`global_denial` yields its usual `global_budget_exhausted` and
`global_guardrail_unknown` categories. The breaker asserts account state and
never the operator's `kill_switch`.

### Where a warning can actually go today

The warning is a callback, so a deployment chooses its sink. On this host the
honest options are the comparison log and the local OTLP file sink. **Grafana
Cloud is not reachable from it**: only `prometheus.scrape` targets forward to
`prometheus.remote_write.grafana_metrics`, while the OTLP receiver path ends at
`otelcol.exporter.file.local`. Alerting in Cloud would need a new scrape target
and an `/etc/alloy/config.alloy` change, which is D1 platform work and a separate
decision.

## Prepared comparison, not a benchmark program

[carveout.py](carveout.py) fixes the comparison record shape and the aggregation
rules now; it runs nothing. Rows are validated against the existing suitability
vocabulary, and `aggregate` reports agreement, an accepted-to-candidate confusion
map, error against human labels when present, and candidate latency. Below
roughly 20 real Tasks it returns `INSUFFICIENT_SAMPLE`, an unlabelled full sample
returns `UNLABELLED`, and it never returns an adoption decision. Monetary cost
stays UNKNOWN on both sides: latency and token counts are the observable proxies.

## Boundary of this result

This is a provider integration and candidate evidence slice. It does not adopt
Jev, change routing defaults, add a supervisor, run the C3 comparison, or claim
measured benefit. Adoption requires that comparison and a human review.

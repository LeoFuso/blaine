# Jev provider candidate and secret delivery

**2026-09-22 — PASS for the integration and one real authenticated invocation.
Jev is NOT adopted and is NOT the default router.**

User-directed increment, not a roadmap-scheduled item. It finishes the
TypeSafe/Jev provider integration against boundaries Blaine already owns, and it
produced a platform standard as a side effect: the credential could not be
delivered safely until [ADR 0023](../decisions/0023-runtime-secret-delivery-and-materialization.md)
removed the secret manager from the runtime path.

Evidence: [Jev candidate](../../experiments/jev-provider-carveout/README.md),
[secret-delivery correction spike](../../experiments/secret-delivery-spike/README.md),
operations in the [secrets runbook](../platform-secrets.md).

## What is live

A real authenticated call against `jev-1.13.0`. In the retained run the
routing suitability judgement agreed with the accepted classifier using
431 input and 49 output tokens, and a continuation-boundary
classification returned `inconclusive` at 0.5 confidence. Both recorded
`applied_to_routing` and `intervention_admitted` false.

Round-trip latency was 701 ms and 416 ms in that run. Latency varies per
invocation, so treat those as observations of the retained evidence rather than a
characteristic of the provider; the evidence file is authoritative.

Monetary cost is **UNKNOWN** on purpose: the provider exposes no cost field, and
estimating one would break the rule that unobservable usage is never invented.

## What remains a candidate

Jev decides nothing. `ShadowClassifier` runs the accepted `ScriptedClassifier`
for the decision and the candidate only for observation, so no routing outcome
can change while it is unadopted. A candidate that fails, times out or answers
outside the vocabulary leaves routing untouched. An offline control asserts the
kernel contains no reference to the provider at all.

Jev adds no vocabulary. It answers the same question `WorkloadClassifier.assess`
answers, returning the existing `UNDERPOWERED` / `JUST_RIGHT` / `OVERKILL`
suitability, and at a continuation boundary it returns the existing closed
`PROCEED` / `ABSTAIN` assessment where its classification is a label rather than
an intervention. Usage uses the existing observed-usage shape.

[C3](../roadmap/001-blaine-development-roadmap.md) is unchanged: adoption still
requires the roughly 20–30 real-Task comparison against Qwen and a human review.
`carveout.py` fixes the comparison record shape and aggregation rules and runs
nothing, returning `INSUFFICIENT_SAMPLE` below the floor and never an adoption
decision.

## Secret delivery, which this increment forced

An agent needing `TYPESAFE_API_KEY` had its credential-store access correctly
blocked. The right conclusion was that a provider should never have had authority
over the secret manager. Bitwarden is now the source of truth and not a runtime
dependency; SecretSpec 0.20.0, pinned by digest, resolves declared secrets behind
one alias; Blaine keeps the consumer allowlist, destination, atomic `0600`
activation, verification, bootstrap withholding and rotation reporting.

The provider code has no Bitwarden, keyring or SecretSpec knowledge. It checks
whether its variable is present and lets the SDK read it.

## Findings worth keeping

The Ubuntu authentication prompts during the session were **not** Bitwarden. They
came from this session's own `systemd-creds` evaluation: systemd 259 runs
unprivileged `systemd-creds` through polkit-authorized helper units, and the
dialog is drawn by `gnome-shell`. The materialization window contains zero
authentication events. That evaluation also created a root-owned host key, which
was reported and later removed with operator authorization.

SecretSpec profiles **extend** the default profile rather than isolating from it,
so each consumer owns a separate manifest and Blaine still filters the resolver's
output to the declared allowlist.

Provider substitution behind the alias was proven live, with the Jev provider
source, consumer declaration, wrapper and manifest byte-identical across a
backend swap. The boundary is addressing: AWS Secrets Manager demands a
per-secret `ref` that is itself backend-coupling, and the Vault and OpenBao path
is inferred from the accepted URI grammar rather than live-tested.

## Limits

No comparison was run and no adoption is claimed. The four-phase acceptance
covers a bounded process; no long-lived service consumes a materialized
credential yet, so rotation restart orchestration is reported but never
exercised. Credentials remain plaintext at rest under an operator-only
directory, which ADR 0023 records as an accepted limitation.

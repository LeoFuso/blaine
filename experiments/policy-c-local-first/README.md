# Policy C — local-first execution with bounded escalation

Evidence for [milestone 042](../../docs/milestones/042-policy-c-local-first-escalation.md)
and [ADR 0024](../../docs/decisions/0024-local-first-execution-with-bounded-escalation.md).

Deterministic fixtures prove the mechanics; this probe exists only to show the
evidence path holding against the real runtime. It owns its own ports, state and
processes, touches no adopted service, and makes **zero paid provider calls**.

## Live probe

[evidence/live-probe.json](evidence/live-probe.json) — real Restate, the adopted
local Qwen deployment, one bounded Task submitted with an external grant.

| Check | Result |
| --- | --- |
| Policy recorded | `local-first-bounded-escalation` |
| Started on the local binding | yes |
| Externally bounded by a grant | yes |
| Effective capabilities | exactly the granted `artifact.write` |
| Escalated | no |
| Final binding | local |
| Routing record discoverable from the append-only event record | yes |
| Task outcome | COMPLETED |

## Deterministic report

[evidence/report.json](evidence/report.json) — produced by
[`scripts/routing-report.py`](../../scripts/routing-report.py) from the probe's
retained evidence, reading content-addressed artifacts discovered through the
event record rather than durable runtime state.

It reported one Task, a local completion rate of 1.0, and
`INSUFFICIENT_SAMPLE`, which is the point: a single observation is reported as
insufficient rather than presented as a finding. Every number carries its
sampling rule and its denominator.

## Reproduction

Needs the adopted loopback serving endpoint on `127.0.0.1:8000`, the
`restate-server` binary, and free ports 41170, 41180, 41190 and 41222.

```sh
python3 experiments/policy-c-local-first/probe.py --output /tmp/policy-c
python3 scripts/routing-report.py --data /tmp/policy-c
```

Offline controls, which start no runtime and perform no inference:

```sh
PYTHONPATH=.:tests python3 -m unittest discover -s tests -p 'test_kernel_routing.py'
```

## Boundary of this result

One Task is not a measurement of local capability. It demonstrates that the
mechanism and the evidence path work end to end. The ratio Policy C exists to
produce needs accumulated real usage, and no production deployment configures an
escalation binding yet, so escalation is currently always denied as unavailable.

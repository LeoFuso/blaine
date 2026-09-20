# Increment 6 — bounded YouTrack read PASS

Hypothesis: cognition can request a Card read through enforcement, receive bounded
coordination data and continue; Card state does not become runtime lifecycle.

The smallest capability is `youtrack.read {issue_id}`. Policy requires the Task
grant; an injected `YouTrackRead` transport additionally checks a deployment-owned
Card allowlist before any connector call. Output selects identity, URL, summary
and bounded description, classified as human coordination with explicit limits.
No Board state machine, writes, comments, transitions or credential handling were
added. Read retries cannot duplicate mutations because the capability is read-only.

Live gate: two durable Tasks, six scripted cognitive turns. The granted Task read
NCP-2 through the existing authenticated YouTrack MCP `get_issue` tool, observed
the result, wrote its independent exact evidence and completed. The denied Task
observed PolicyDecision denial and completed permitted work; no Card transport
call occurred for it. Both completion evaluations remain independent of Card state.
33 focused tests pass, including target-scope rejection before transport and
bounded projection without Card-to-Task lifecycle promotion.

The native connector is session-hosted, not credentialed inside the runtime.
For this empirical probe, the capability published a controlled read request;
the experiment controller executed the actual MCP read and supplied its raw JSON
response. That is a **live connector call through a controlled bridge**, not an
autonomous production MCP transport and not an injected synthetic Card response.
The test bridge lives only under experiments; production wiring remains injected.
No LLM inference was used or claimed. Independent unit tests use fake transport.
Read discovery found NCP-2 by a bounded Blaine query; no Card was modified.

[Summary](../../experiments/kernel-increment-6/evidence/summary.json),
[exact connector response](../../experiments/kernel-increment-6/evidence/connector-raw.json),
[capability results](../../experiments/kernel-increment-6/evidence/capabilities.jsonl),
[cognitive observations](../../experiments/kernel-increment-6/evidence/cognition.jsonl),
[tests](../../experiments/kernel-increment-6/evidence/tests.txt).

Changed: new `youtrack.py`, a capability name/admission/dispatch branch, declarative
model schema guidance, three tests and isolated probe files. No workflow, Task
state, completion or memory changes. Architecture deviations: none. Connector
transport deployment remains an explicit seam, not an unexplained failure.

Gate passed. Exact next increment: **7**, one existing external worker/harness,
bounded packet, interruption/replacement and independent completion verification.

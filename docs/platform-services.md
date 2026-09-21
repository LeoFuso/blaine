# D1 service adoption and prepared reboot proof

**2026-09-21: D1.A/B/C/D live adoption PASS within the evidence below. D1 remains
IN PROGRESS: D1.G host reboot is not executed; D1.F backup remains PAUSED.**
This accepts the actual runtime and its bounded integrations, not general Daily
Driver productivity or a complete backup. Rootless migration commit `16fbb16`
and ADR 0019 are preserved.

## Automatic startup and readiness

The existing linger-enabled user manager starts rootless Docker, infrastructure,
and five enabled user services without an interactive terminal or sudo:

| Unit | Endpoint/readiness | Runtime and state |
|---|---|---|
| `blaine-embedding.service` | `127.0.0.1:8001/health`, `/v1/models`, real vector request | Pinned BGE-M3/vLLM environment |
| `blaine-generation.service` | `127.0.0.1:8000/health`, `/v1/models`, JSON/tools/generation | Pinned Qwen/vLLM environment |
| `blaine-mirix.service` | `127.0.0.1:8531/health`, retained semantic search | Existing MIRIX checkout, PostgreSQL identity |
| `blaine-restate.service` | `127.0.0.1:49070/deployments`, ingress `48080` | Stable server binary and preserved native journal |
| `blaine-runtime.service` | Actual endpoint `49080`, registered `CognitiveTaskV1`, inspect/run | `runtime.personal_runtime`, immutable ArtifactStore |

Native PostgreSQL 18, Redis and Alloy retain their existing service identities.
`docker.service` and `blaine-infra.service` are enabled user units; their four
containers have real application health checks. User services use bounded
readiness polling and restart-on-failure. They cannot order against native units
in the system manager. Startup readiness is not continuous dependency monitoring.

One ordering constraint is real: BGE-M3 must be ready before Qwen profiles global
GPU memory. Concurrent cold model startup distorted vLLM's available-memory
calculation. This does not prevent independent restarts after initialization.
The application waits for actual inference/MIRIX/Restate readiness; no single
strict boot chain is imposed on all infrastructure.

## Accepted inference

| Item | Accepted value |
|---|---|
| Generation checkpoint | `nvidia/Qwen3.8-27B-NVFP4` |
| Revision | `482ca0f3832238542f8f5295dde86b5f22711d80` |
| Generation boundary | **131072 total tokens**, one sequence, FP8 E4M3 KV |
| Embedding checkpoint | `BAAI/bge-m3` |
| Revision | `5617a9f61b028005a4858fdac845db406aefb181` |
| Embedding output/context | 1024 dimensions / 8192 tokens |
| vLLM | `0.29.1rc1.dev401+gc3b484463`; commit `c3b48446349569512749db7f6e2164aa8a33437d` |
| Torch / Python | `2.13.0+cu132` / `3.13.15` |
| CUDA | Build/runtime 13.2; runtime API 13020; nvcc 13.2.78; runtime wheel 13.2.75 |
| GPU / driver | RTX 5090, 32607 MiB / 595.91.07 |
| Observed total VRAM | 29254–29821 MiB during acceptance; shared with desktop |

The final idle observation was 29254 MiB VRAM, about 44 GiB host RAM available,
and zero swap/OOM events in all five service cgroups. This is an observation,
not a reservation or a long-term stability guarantee.

A real request used 130944 input tokens plus an output allowance of 128, completed
in 34.458 seconds, and retrieved three separated markers. This is capacity and
bounded behavior evidence, not a claim of arbitrary 128k reasoning quality or a
saturation benchmark. No context fallback was necessary. One generation plus
embeddings coexist; two simultaneous generations are not a requirement.

Exact arguments/resource limits are in [candidate.json](../infra/inference/candidate.json)
and [deployment notes](../infra/inference/README.md). GPU budgets are 0.80/0.08;
CPU/RAM/compiler limits protect the rest of the platform. The previous host OOM
killed Chrome and a CUDA compiler. Single-job compilation and cgroup limits now
bound that path; no CPU weight offload or hybrid-model investigation was performed.

Existing vLLM/Torch/CUDA artifacts were reused. Isolated CUDA wheel aliases
(`lib64`, unversioned libcudart/cuBLAS links) enabled FlashInfer JIT. Seven cached
compiled-library hashes, AOT reuse and exact packages are recorded in
[runtime versions](../experiments/d1-service-adoption/evidence/runtime-versions.json).
Do not remove these caches or the retained Qwen3.5-9B rollback artifacts.

Goose 1.50.1 now normally uses the shared OpenAI-compatible loopback Qwen endpoint
and 131072 context. Existing Ollama configuration is preserved; it has no loaded
model. The private configuration backup is
`~/.config/goose/config.yaml.pre-d1-service-adoption`. Both the actual Goose CLI
and `GooseWorker` completed useful source/configuration interactions. No cloud
provider call was needed. See [21 inference checks](../experiments/d1-service-adoption/evidence/inference-summary.json).

## Preserved MIRIX

MIRIX remains semantic memory, never Task lifecycle state. The actual clean
checkout is `~/workspace/mirix`, revision
`8cb06a62bbb7c478beb33dd4f2815696a72df482`, using its existing `.venv` Python
3.13.15, package 0.1.0 ([dependency versions](../experiments/d1-service-adoption/evidence/mirix-runtime-versions.json)). The original private `~/.mirix/config` (0600, directory 0700) supplies the
same PostgreSQL database/role `mirix` on `127.0.0.1:5432`; credentials stay outside
Git and are not copied into units. Native PostgreSQL stores the data. Redis and
Langfuse integration remain disabled in this MIRIX environment.

All seven original agent identities remain. Only generation model/context changed
to the accepted Qwen/131072; BGE-M3 endpoint/config stayed intact. Private original
LLM configurations are retained under
`~/.local/share/blaine/service-adoption-rollback/mirix-models`.

The original three semantic memories retain their exact content hashes. The new
synthetic `sem_CWMT` was inserted through the real API/model tools and retrieved
through embeddings before and after service restart, with identical content.
The first HTTP "processed" receipt did not establish storage; acceptance requires
readback. Search uses the actual cosine-distance threshold 0.5; 0.3 hid the new
item. See [MIRIX evidence](../experiments/d1-service-adoption/evidence/mirix-summary.json).

## Preserved Restate and actual Blaine runtime

Restate server **1.7.9**, SHA256
`388336a1a3929c4ae20701d3c4d587af3ff348b9f81f97a3774515826c40aae5`, runs as the
operator. Blaine uses Python **3.14.4**, Restate SDK **1.0.5**, Hypercorn **0.17.3**,
ACP **0.12.1**. [Runtime](../infra/services/requirements.lock) and
[operations](../infra/services/operations-requirements.lock) dependencies are pinned.

Inventory found no running Restate owner. The last accepted D2 native journal and
runtime data in `~/workspace/blaine-personal-agent/.local/d2-post-sync-native/`
were copied offline, with source/destination file hashes verified, to:

| Path under `~/.local/share/blaine/runtime/` | Meaning |
|---|---|
| `restate-data/` | Restate's authoritative durable Task journal/state |
| `data/artifacts/` | Existing authoritative immutable produced artifacts/evidence |
| `data/fixture.sqlite` | Bounded side-effect fixture, not a Task ledger |
| `data/events.jsonl` | Existing forensic execution events, not lifecycle authority |
| `app/runtime/`, `env/`, `bin/restate-server` | Stable deployment independent of the feature worktree |
| `ops/` | Persistent Ansible/boto3 validation environment |

Original journals, artifacts and older `.local/002` state remain untouched. The
retained deployment points to `http://127.0.0.1:49080/` and `CognitiveTaskV1`.
All five existing D2 Task identities remained inspectable with identical state.
New real Tasks proved completed artifact retrieval, preserved WAITING across
Restate and Blaine restarts, and explicit human-response resume to COMPLETED.
A separate cognitive Task recalled the MIRIX marker and produced its exact hash
without the marker appearing in its objective. This exercises the actual accepted
`runtime.personal_runtime`, not a probe service.

Operator configuration at `~/.config/blaine/services/runtime.json` wires existing
LocalModelCognition, MirixContext and GooseWorker adapters. The MIRIX client/user
binding remains the accepted `client-df3da0d9` / `probe-leofuso`; broader personal
memory onboarding is not inferred. `~/.local/bin/blaine-agent` is the stable actual
ACP stdio client entrypoint. Clients may come and go while Tasks remain in Restate.

**Implementation boundary:** PostgreSQL plus Blaine Object Storage remain the
architectural durable knowledge/artifact brain. The adopted kernel's current
ArtifactStore is still local immutable files; there is no accepted S3 ArtifactStore
adapter to enable here. The S3 reboot marker independently verifies object storage.
No artifact authority is silently moved or replaced, and no new database ledger
is introduced.

**Shutdown limitation:** with the existing Hypercorn/Python combination, SIGTERM
shutdown exceeded the unit's 60-second stop bound. systemd killed that process,
and the same durable Tasks/artifacts recovered; explicit resume passed. Graceful
HTTP shutdown is not claimed. No second runtime hides this behavior.

## Observability, security and operation

Existing journald captures all five services. Alloy's local-only allowlist now
includes those exact user units at UID 1000, alongside rootless Docker/infra.
Existing host CPU/RAM/load/disk/network/systemd metrics and Alloy self metrics
continue every 30 seconds, with bounded local OTLP retention. GPU use and cgroup
OOM/swap counters are sampled in acceptance evidence; there is no dedicated GPU
exporter, new alerting project or automatic end-to-end Task health monitor.
Grafana Cloud delivery remains inactive. The [Fleet slice](platform-grafana-cloud.md)
proved BWS/API access but STOPPED activation on Alloy 1.19.2 offline-start failure;
the exact local collector config was restored. Backups are still PAUSED, timer disabled/inactive.

Routine operator commands need no sudo:

```sh
systemctl --user status blaine-runtime blaine-restate blaine-mirix blaine-generation blaine-embedding
journalctl --user -u blaine-runtime -u blaine-restate --since '15 minutes ago'
~/.local/bin/blaine-agent  # ACP stdio; connect using an ACP-compatible client
```

Desired state is in [user units](../infra/systemd/user),
[services playbook](../infra/ansible/services.yml), [launchers](../infra/services).
The playbook stages by default; `-e blaine_activate=true` enables/starts only after
accepted evidence and an existing preserved journal are present. It never creates
a new journal, migrates data, installs dependencies or copies secrets implicitly.
Runtime source changes require a deliberate controlled restart and validation.
Scratch staging uses a bounded `/tmp/blaine-d1-*` prefix and never activates.

Normal operation is non-root. Bounded Alloy maintenance used existing temporary
sudo authorization; sudoers was not changed or removed. The operator must remove
and verify that temporary rule separately. No secret was printed or committed.

## D1.G — later human-authorized reboot procedure

**No reboot is authorized by this runbook. None occurred during this adoption.**
The following procedure is ready for the operator's later explicit authorization:

1. From `~/workspace/blaine`, record current read-only checks:
   `~/.local/share/blaine/runtime/ops/bin/python infra/services/reboot-check.py --output /tmp/blaine-d1-before-reboot.json`.
   Inspect PASS and the evidence below. Do not recreate missing fixtures to pass.
2. After explicit human authorization, the operator runs `systemctl reboot`.
3. Log in without manually starting services. From the same repository run:
   `~/.local/share/blaine/runtime/ops/bin/python infra/services/reboot-check.py --after-reboot --output /tmp/blaine-d1-after-reboot.json`.
   The verifier waits up to 1500 seconds for automatic readiness, requires a changed
   boot ID, and checks the same identities, states and hashes. It does not start,
   restart, seed or respond to anything.
4. Check native Alloy readiness and local telemetry. Fleet reconnect is optional
   supporting evidence only if separately accepted/activated before that reboot;
   it is currently STOPPED and is never a Blaine correctness dependency.
   Preserve verifier output, process ownership evidence and relevant boot journals.
   Run the bounded inference smoke if investigating a failed model check. Record
   STOP on missing/changed state; never hide it with a second runtime or new marker.
5. Only accepted post-reboot evidence can close D1.G. Backup remains PAUSED even
   if D1.G passes; reboot acceptance is not backup/restore acceptance.

| Persistent evidence | Identity and expected result |
|---|---|
| Object | Bucket `blaine-artifacts`, key `d1-service-adoption/0d7e1cc1b2934465826f4390b0299582.txt`; exact content/hash in [fixture](../experiments/d1-service-adoption/evidence/object-fixture.json) |
| Semantic memory | `sem_CWMT`, project `D1Persistence_61e17b6f3500`, fact `D1_AMBER_61E17B6F3500`; identical normalized content hash |
| Human wait | `task-f14cf0feca5d864d6ec1ab5a99e4a93ba858267b05f060e6d8bb7dbf425dae92` remains **WAITING**, same pending request/digest; do not respond |
| Explicitly resumed Task | `task-5e7425160c23459ed8b873e9bdf472253c547735c5e86045a6f7b8c248785e5e` remains COMPLETED |
| Cognitive recall Task | `task-c07a288d19a208d0e791c192c26d60cd3e0ad520e2a2bedbdd53810a365a8708` remains COMPLETED with exact marker artifact |

[Pre-reboot PASS](../experiments/d1-service-adoption/evidence/pre-reboot.json),
[durable Task proofs](../experiments/d1-service-adoption/evidence/durable-summary.json),
[cognitive integration](../experiments/d1-service-adoption/evidence/cognition-summary.json).
The saved pre-reboot boot ID is the baseline; it must change for D1.G. After
recording the unchanged WAITING state, the operator can explicitly authorize a
synthetic `YES` through the actual ACP command
`respond task-f14cf0feca5d864d6ec1ab5a99e4a93ba858267b05f060e6d8bb7dbf425dae92: YES`.
Then record inspection/result evidence showing that same Task completed. This is
a separate authorized response, never an automatic consequence of reboot; retain
the earlier WAITING evidence. The read-only baseline verifier will intentionally
stop matching once that Task is legitimately answered.

# Graphify carveout probe

Read the [findings](../../docs/research/graphify-carveout.md) first. These scripts
record observations, including failures; they are not an integration or an
acceptance suite for a future Blaine capability.

Upstream: `https://github.com/Graphify-Labs/graphify`, commit
`b9cd9570728a5ff3485d2a1e36fe9a1272a368ae` (package `graphifyy` 0.9.64).
The unchanged checkout used here is the sibling `../graphify-upstream`.
Corpus: Blaine commit `da6654e3a008b7e6be4f7ad54a5c4323bcb8f090`.
The corpus is a disposable local clone; uncommitted working-tree changes are
deliberately outside this pinned observation. No Blaine runtime module is executed.

`task-request.json` is an **unsubmitted** TaskSpec. No Task creation binding was
available in this session; this file is neither runtime state nor a task ledger.

## Reproduce

Run from the Blaine repository root on Linux. The observed environment was
CPython 3.12.14; the exact dependency resolution is in `requirements.lock`.
Installing dependencies needs package-index access. Running the probes needs no
network, model, credentials, database, Git hook, or Blaine runtime service.

Prepare the sibling checkout at the pinned SHA, without changing its source:

```bash
git clone https://github.com/Graphify-Labs/graphify ../graphify-upstream
git -C ../graphify-upstream checkout --detach b9cd9570728a5ff3485d2a1e36fe9a1272a368ae
```

Skip cloning when that checkout already exists; verify its SHA and clean status.
Keep its path fixed for the follow-up scripts.

```bash
uv --cache-dir experiments/graphify-carveout/.cache venv --python 3.12 experiments/graphify-carveout/.venv
uv --cache-dir experiments/graphify-carveout/.cache pip sync --python experiments/graphify-carveout/.venv/bin/python experiments/graphify-carveout/requirements.lock

export PYTHONDONTWRITEBYTECODE=1
export GRAPHIFY_QUERY_LOG_DISABLE=1
export PYTHONPATH="$PWD/experiments/graphify-carveout/offline:$PWD/../graphify-upstream"

experiments/graphify-carveout/.venv/bin/python experiments/graphify-carveout/probe.py
experiments/graphify-carveout/.venv/bin/python experiments/graphify-carveout/boundary_probe.py
experiments/graphify-carveout/.venv/bin/python experiments/graphify-carveout/boundary_probe.py --factory
experiments/graphify-carveout/.venv/bin/python experiments/graphify-carveout/freshness_probe.py
```

Each run overwrites its retained result JSON and creates a fresh ignored `work/`
directory. Run `probe.py` before `boundary_probe.py`: the latter uses the former's
saved graph path. Absolute temporary paths and timings vary across runs.
The primary probe checks the upstream SHA. Follow-ups use that same checkout;
do not update it between commands.

`offline/sitecustomize.py` denies Python IPv4/IPv6 connection attempts, including
Python subprocesses. It is a probe guard, not an OS sandbox. The semantic test
replaces the model transport with a synthetic response; **no Qwen or other model
is invoked**. An Ollama-oriented informational message from upstream does not
mean an actual request was sent.

The package is imported directly from upstream rather than installed into the
environment. Consequently Graphify's package-version cache namespace reports
`unknown`; a pinned checkout and fresh disposable caches avoid cross-version
reuse in this experiment. This is not evidence for upgrade-safe production caches.

## Retained evidence

| File | What it records |
|---|---|
| `results.json` | Pinned Blaine build, source checks, queries, mutation/reconciliation, concurrent readers, branch checkout and synthetic stale semantics |
| `boundary-results.json` | Manifest/SQL/Java/config fixtures, path-selection failure, stdio attempt and stubbed semantic provenance |
| `factory-results.json` | Stdio control without Graphify's CLI input wrapper; actual MCP HTTP ASGI initialize/list/get-node responses without a network listener |
| `freshness-results.json` | Markdown frontmatter cache staleness, unchanged-caller/new-callee invalidation gap, root relocation IDs |
| `upstream-checks.txt` | Targeted upstream tests and observed result |

`mcp_factory_server.py` is a diagnostic launcher around the unchanged Graphify
factory and SDK stdio transport. It is not a proposed adapter. The HTTP control
uses upstream's actual ASGI app with stateless JSON responses, in process.
It does not establish network deployment, authentication or stateful-session behavior.

The initial `boundary-results.json` predates addition of the HTTP control; the
retained HTTP evidence is in `factory-results.json`. A fresh default run also
records HTTP evidence. Stdio timed out in both launch variants; the probes record
that observation without asserting its cause or making it an expected pass.

Generated graphs, reports, HTML, manifests, snapshots, caches and disposable Git
clones remain in ignored `work/`. They are reproducible, not vendored artifacts.
The original graph's SHA-256 is recorded in `results.json` for local inspection.
The scripts modify only disposable corpora and the retained experiment results.

## Targeted upstream checks

With the environment above, run from this experiment's ignored work directory
so any incidental test outputs stay isolated:

```bash
mkdir -p experiments/graphify-carveout/work/upstream-tests-cwd
GRAPHIFY_TEST_ROOT="$PWD/../graphify-upstream/tests"
(
  cd experiments/graphify-carveout/work/upstream-tests-cwd
  ../../.venv/bin/python -m pytest -q -p no:cacheprovider --basetemp=../pytest-tmp \
    "$GRAPHIFY_TEST_ROOT/test_java_member_calls.py" \
    "$GRAPHIFY_TEST_ROOT/test_java_type_resolution.py" \
    "$GRAPHIFY_TEST_ROOT/test_go_qualified_resolution.py" \
    "$GRAPHIFY_TEST_ROOT/test_rust_self_member_calls.py" \
    "$GRAPHIFY_TEST_ROOT/test_manifest_ingest.py" \
    "$GRAPHIFY_TEST_ROOT/test_markdown_code_spans.py" \
    "$GRAPHIFY_TEST_ROOT/test_inferred_confidence_rubric.py"
)
```

Observed: **94 passed in 0.94s**. This bounded check does not validate all supported
languages, semantic inference quality, large repositories or transport compatibility.

"""Run unchanged upstream functions on disposable corpora; never import Blaine runtime.

Results are observations (including negative findings), not an adoption test suite.
See README.md for the offline invocation and pinned environment.
"""
from __future__ import annotations

import ast
from collections import Counter
import copy
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import select
import shutil
import subprocess
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
UPSTREAM_SHA = "b9cd9570728a5ff3485d2a1e36fe9a1272a368ae"
CORPUS_SHA = "da6654e3a008b7e6be4f7ad54a5c4323bcb8f090"
UPSTREAM = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else REPO.parent / "graphify-upstream"
(HERE / "work").mkdir(exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix="run-", dir=HERE / "work"))
CORPUS = WORK / "corpus"
OUT = WORK / "graphify-out"
os.environ["GRAPHIFY_OUT"] = str(OUT)
os.environ["GRAPHIFY_MAX_WORKERS"] = "1"
os.environ["GRAPHIFY_NO_TIPS"] = "1"
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([str(HERE / "offline"), str(UPSTREAM)])
sys.path.insert(0, str(UPSTREAM))


def command(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=90)
    if p.returncode:
        raise RuntimeError(f"{args}: {p.returncode}\n{p.stderr}\n{p.stdout}")
    return p.stdout.strip()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


assert command(["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"]) == UPSTREAM_SHA
command(["git", "clone", "--shared", "--no-checkout", str(REPO), str(CORPUS)])
command(["git", "-C", str(CORPUS), "checkout", "--detach", CORPUS_SHA])
os.chdir(CORPUS)

from graphify import extract as extraction
from graphify.analyze import god_nodes, graph_diff
from graphify.build import build_from_json
from graphify.cluster import cluster
from graphify.detect import detect, detect_incremental, save_manifest
from graphify.export import to_json
from graphify.serve import _GraphContextCache, _load_graph, _query_graph_text, _shortest_path_text
from graphify.watch import _rebuild_code

results = {
    "upstream_sha": UPSTREAM_SHA,
    "corpus_sha": CORPUS_SHA,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "work_directory": str(WORK),
    "packages": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
    "network_guard": "offline/sitecustomize.py denies IPv4/IPv6 connect in this process and Python children",
    "checks": {},
}


def check(name, condition, evidence):
    results["checks"][name] = {"observed": bool(condition), "evidence": evidence}


def summary(G):
    return {
        "type": type(G).__name__, "nodes": len(G), "edges": G.number_of_edges(),
        "node_origins": dict(Counter(d.get("_origin", "MISSING") for _, d in G.nodes(data=True))),
        "edge_origins": dict(Counter(d.get("_origin", "MISSING") for *_, d in G.edges(data=True))),
        "confidence": dict(Counter(d.get("confidence", "MISSING") for *_, d in G.edges(data=True))),
        "relations": dict(Counter(d.get("relation", "MISSING") for *_, d in G.edges(data=True))),
    }


def named(G, label, source=None):
    return [n for n, d in G.nodes(data=True) if d.get("label", "").rstrip("()") == label
            and (source is None or d.get("source_file") == source)]


def matching_edges(G, src_file=None, tgt_file=None, relation=None):
    return [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)
            if (src_file is None or G.nodes[u].get("source_file") == src_file)
            and (tgt_file is None or G.nodes[v].get("source_file") == tgt_file)
            and (relation is None or d.get("relation") == relation)]


started = time.perf_counter()
scan = detect(CORPUS, cache_root=WORK)
paths = [Path(f) for files in scan["files"].values() for f in files
         if extraction._get_extractor(Path(f)) is not None]
raw = extraction.extract(paths, root=CORPUS, cache_root=WORK, parallel=False)
write(WORK / "initial-extraction.json", raw)
G = build_from_json(copy.deepcopy(raw), directed=True, root=CORPUS)
communities = cluster(G)  # Louvain fallback; no Leiden extra installed.
OUT.mkdir(parents=True, exist_ok=True)
assert to_json(G, communities, str(OUT / "graph.json"), built_at_commit=CORPUS_SHA)
save_manifest(scan["files"], str(OUT / "manifest.json"), kind="ast", root=CORPUS)
(OUT / ".graphify_root").write_text(str(CORPUS))
shutil.copyfile(OUT / "graph.json", WORK / "initial-graph.json")
initial_seconds = time.perf_counter() - started
loaded = _load_graph(str(OUT / "graph.json"))
results["initial"] = {
    "detected_by_type": {k: len(v) for k, v in scan["files"].items()},
    "extracted_files": len(paths), "raw_nodes": len(raw["nodes"]), "raw_edges": len(raw["edges"]),
    "failed_sources": raw["failed_sources"], "unclassified": [str(Path(p).relative_to(CORPUS)) for p in scan["unclassified"]],
    "graph": summary(loaded), "communities": len(communities),
    "seconds": initial_seconds, "json_bytes": (OUT / "graph.json").stat().st_size,
    "input_tokens": raw["input_tokens"], "output_tokens": raw["output_tokens"],
    "artifact_sha256": digest(OUT / "graph.json"),
    "god_nodes": god_nodes(G)[:3],
}
check("json_roundtrip", set(G.nodes) == set(loaded.nodes) and G.number_of_edges() == loaded.number_of_edges(), summary(loaded))

# Independent truth uses Python's AST and literal files, never the Blaine runtime.
source = (CORPUS / "runtime/app.py").read_text()
app_ast = ast.parse(source)
truth_imports = [{"module": n.module, "names": [a.name for a in n.names], "line": n.lineno}
                 for n in ast.walk(app_ast) if isinstance(n, ast.ImportFrom)]
truth_calls = [{"name": n.func.id, "line": n.lineno} for n in ast.walk(app_ast)
               if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
app_to_task = matching_edges(loaded, "runtime/app.py", "runtime/task.py")
check("runtime_import_and_calls", any(e["relation"] == "imports" for e in app_to_task)
      and any(e["relation"] == "calls" for e in app_to_task),
      {"source_imports": truth_imports, "source_calls": truth_calls, "graph_edges": app_to_task})
doc_edges = [e for e in matching_edges(loaded, relation="references")
             if loaded.nodes[e["source"]].get("source_file", "").endswith(".md")
             and loaded.nodes[e["target"]].get("source_file", "").startswith("runtime/")]
check("docs_reference_runtime", bool(doc_edges), doc_edges[:8])
results["queries"] = {}
for question in ("validate_request", "durable Task execution verification", "project knowledge retrieval", "runtime app summarize_objective"):
    t = time.perf_counter()
    answer = _query_graph_text(loaded, question, token_budget=900, graph_path=str(OUT / "graph.json"))
    results["queries"][question] = {"seconds": time.perf_counter() - t, "answer": answer}
results["shortest_path"] = _shortest_path_text(loaded, {
    "source": named(loaded, "run", "runtime/app.py")[0],
    "target": named(loaded, "validate_request", "runtime/task.py")[0],
})
results["requirements_coverage"] = {
    "source": (CORPUS / "runtime/requirements.txt").read_text(),
    "nodes": [dict(id=n, **d) for n, d in loaded.nodes(data=True) if d.get("source_file") == "runtime/requirements.txt"],
}

# Cache reuse measured by observing the real per-file parser dispatcher.
parse_invocations = []
original_parser = extraction._extract_single_file


def counted(args):
    parse_invocations.append(str(args[1]))
    return original_parser(args)


extraction._extract_single_file = counted
t = time.perf_counter()
again = extraction.extract(paths, root=CORPUS, cache_root=WORK, parallel=False)
results["warm_extract"] = {"seconds": time.perf_counter() - t, "parser_calls": list(parse_invocations),
                           "same_raw": raw == again}
extraction._extract_single_file = original_parser

# Actual CLI code-only path must stand alone as well (separate output).
cli_out = WORK / "cli-output"
env = dict(os.environ, GRAPHIFY_OUT=str(cli_out))
p = subprocess.run([sys.executable, "-m", "graphify", "extract", str(CORPUS), "--code-only"],
                   env=env, text=True, capture_output=True, timeout=90)
results["cli_code_only"] = {"returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
if (cli_out / "graph.json").exists():
    results["cli_code_only"]["graph"] = summary(_load_graph(str(cli_out / "graph.json")))

# Real stdio JSON-RPC MCP: no HTTP listener, no assistant registration.
server = subprocess.Popen([sys.executable, "-m", "graphify.serve", str(OUT / "graph.json")],
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          text=True, bufsize=1)
rpc_id = 0


def rpc(method, params=None):
    global rpc_id
    rpc_id += 1
    server.stdin.write(json.dumps({"jsonrpc": "2.0", "id": rpc_id, "method": method, "params": params or {}}) + "\n")
    server.stdin.flush()
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if not select.select([server.stdout], [], [], max(0, deadline - time.monotonic()))[0]:
            break
        line = server.stdout.readline()
        if not line:
            raise RuntimeError("MCP closed stdout: " + server.stderr.read())
        response = json.loads(line)
        if response.get("id") == rpc_id:
            return response
    raise TimeoutError(method)


try:
    results["mcp"] = {"initialize": rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                     "clientInfo": {"name": "blaine-carveout-probe", "version": "1"}})}
    server.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    server.stdin.flush()
    tools = rpc("tools/list")
    results["mcp"]["tools"] = [t["name"] for t in tools.get("result", {}).get("tools", [])]
    results["mcp"]["stats"] = rpc("tools/call", {"name": "graph_stats", "arguments": {}})
    results["mcp"]["query"] = rpc("tools/call", {"name": "query_graph", "arguments": {"question": "validate_request", "token_budget": 500}})
    results["mcp"]["node"] = rpc("tools/call", {"name": "get_node", "arguments": {"label": named(loaded, "validate_request", "runtime/task.py")[0]}})
    results["mcp"]["bad_argument"] = rpc("tools/call", {"name": "query_graph", "arguments": {"question": "validate_request", "depth": "invalid"}})
    results["mcp"]["resources"] = rpc("resources/list")
except Exception as exc:
    results.setdefault("mcp", {})["error"] = repr(exc)
finally:
    server.stdin.close()
    try:
        server.wait(timeout=8)
    except subprocess.TimeoutExpired:
        server.terminate()
        server.wait(timeout=8)

# Changed caller -> unchanged callee, deletion, symbol rename, and file move.
task_path = CORPUS / "runtime/task.py"
task_original = task_path.read_text()
app_path = CORPUS / "runtime/app.py"
app_original = app_path.read_text()
app_path.write_text(app_original + "\n\ndef carveout_probe_only(request):\n    return validate_request(request)\n")
delta = detect_incremental(CORPUS, str(OUT / "manifest.json"), kind="ast")
ok = _rebuild_code(CORPUS, changed_paths=[app_path])
after = _load_graph(str(OUT / "graph.json"))
probe_nodes = named(after, "carveout_probe_only", "runtime/app.py")
call_edges = [e for e in matching_edges(after, "runtime/app.py", "runtime/task.py", "calls") if e["source"] in probe_nodes]
check("changed_caller_to_unchanged_callee", ok and bool(call_edges), {
    "changed": [str(Path(p).relative_to(CORPUS)) for fs in delta["new_files"].values() for p in fs], "edges": call_edges})

task_path.write_text(task_original.replace("def validate_request(", "def validate_request_renamed("))
ok = _rebuild_code(CORPUS, changed_paths=[task_path])
after_rename = _load_graph(str(OUT / "graph.json"))
check("renamed_symbol_removes_old_definition", ok and not named(after_rename, "validate_request", "runtime/task.py")
      and bool(named(after_rename, "validate_request_renamed", "runtime/task.py")), {
    "old": named(after_rename, "validate_request", "runtime/task.py"),
    "new": named(after_rename, "validate_request_renamed", "runtime/task.py"),
    "incoming_from_unchanged_app": matching_edges(after_rename, "runtime/app.py", "runtime/task.py", "calls")})

moved = CORPUS / "runtime/task_moved.py"
task_path.rename(moved)
ok = _rebuild_code(CORPUS, changed_paths=[task_path, moved])
after_move = _load_graph(str(OUT / "graph.json"))
old_nodes = [n for n, d in after_move.nodes(data=True) if d.get("source_file") == "runtime/task.py"]
check("moved_file_drops_old_nodes", ok and not old_nodes, {"old_nodes": old_nodes, "new_nodes":
      [n for n, d in after_move.nodes(data=True) if d.get("source_file") == "runtime/task_moved.py"]})
moved.unlink()
ok = _rebuild_code(CORPUS, changed_paths=[moved])
after_delete = _load_graph(str(OUT / "graph.json"))
check("deleted_file_drops_nodes", ok and not any(d.get("source_file") == "runtime/task_moved.py" for _, d in after_delete.nodes(data=True)), summary(after_delete))

# Restore only disposable tracked files; no commit is created.
command(["git", "restore", "--source", CORPUS_SHA, "--worktree", "--", "."], CORPUS)
assert _rebuild_code(CORPUS, force=True)
cache = _GraphContextCache(2)
old_context, _ = cache.load(str(OUT / "graph.json"), pinned=True)
task_path.write_text(task_original + "\n\ndef concurrent_probe_sentinel():\n    return 1\n")
log = (WORK / "concurrent-update.log").open("w")
updater = subprocess.Popen([sys.executable, "-m", "graphify", "update", str(CORPUS)], stdout=log, stderr=log)
read_counts = Counter()
read_errors = []
deadline = time.monotonic() + 60
while updater.poll() is None and time.monotonic() < deadline:
    try:
        d = json.loads((OUT / "graph.json").read_text())
        read_counts[(len(d["nodes"]), len(d.get("links", d.get("edges", []))))] += 1
    except Exception as exc:
        read_errors.append(repr(exc))
if updater.poll() is None:
    updater.terminate()
updater.wait(timeout=8)
log.close()
new_context, _ = cache.load(str(OUT / "graph.json"), pinned=True)
check("concurrent_reads_parse_during_update", updater.returncode == 0 and bool(read_counts) and not read_errors,
      {"returncode": updater.returncode, "reads_by_size": {str(k): v for k, v in read_counts.items()}, "errors": read_errors})
check("query_cache_hot_reload", new_context is not old_context and bool(named(new_context, "concurrent_probe_sentinel")),
      {"old_has_sentinel": bool(named(old_context, "concurrent_probe_sentinel")), "new_has_sentinel": bool(named(new_context, "concurrent_probe_sentinel"))})

# Switch existing Git revisions without hooks or creating a commit.
command(["git", "restore", "--source", CORPUS_SHA, "--worktree", "--", "."], CORPUS)
previous = command(["git", "rev-parse", CORPUS_SHA + "^"], CORPUS)
command(["git", "checkout", "--detach", previous], CORPUS)
ok = _rebuild_code(CORPUS, force=True)
back_data = json.loads((OUT / "graph.json").read_text())
check("checkout_stamp_follows_revision", ok and back_data.get("built_at_commit") == previous,
      {"checked_out": previous, "built_at_commit": back_data.get("built_at_commit"), "nodes": len(back_data["nodes"])})
command(["git", "checkout", "--detach", CORPUS_SHA], CORPUS)
assert _rebuild_code(CORPUS, force=True)

# Controlled mixed-provenance input. No LLM ran: the semantic record is synthetic.
mixed = _load_graph(str(OUT / "graph.json"))
mixed.add_node("synthetic_semantic_claim", label="Synthetic summary before doc edit", file_type="concept",
               source_file="docs/architecture.md", source_location="L1", _origin="semantic")
assert to_json(mixed, {}, str(OUT / "graph.json"), force=True, built_at_commit=CORPUS_SHA)
doc = CORPUS / "docs/architecture.md"
doc.write_text(doc.read_text() + "\n## Carveout Fresh Heading\n\nProbe-only content.\n")
ok = _rebuild_code(CORPUS, changed_paths=[doc])
mixed_after = _load_graph(str(OUT / "graph.json"))
results["mixed_semantic_update"] = {
    "synthetic_not_llm": True, "update_return": ok,
    "semantic_claim_retained": "synthetic_semantic_claim" in mixed_after,
    "new_heading_present": bool(named(mixed_after, "Carveout Fresh Heading")),
    "semantic_record": mixed_after.nodes.get("synthetic_semantic_claim"),
}

# Lossy builder and uncalibrated provenance controls.
control_nodes = [{"id": s, "label": s, "file_type": "code", "source_file": "control.py", "source_location": "L1", "_origin": "ast"} for s in ("a", "b")]
control_edges = [
    {"source": "a", "target": "b", "relation": "calls", "confidence": "INFERRED", "_origin": "ast"},
    {"source": "a", "target": "b", "relation": "references", "confidence": "EXTRACTED", "_origin": "ast"},
    {"source": "b", "target": "a", "relation": "calls", "confidence": "INFERRED", "_origin": "ast"},
]
results["builder_controls"] = {}
for directed in (False, True):
    g = build_from_json({"nodes": copy.deepcopy(control_nodes), "edges": copy.deepcopy(control_edges)}, directed=directed)
    results["builder_controls"][str(directed)] = {"input_edges": control_edges, "surviving_edges": [dict(source=u, target=v, **d) for u, v, d in g.edges(data=True)]}
results["artifacts"] = [str(p.relative_to(OUT)) for p in sorted(OUT.rglob("*")) if p.is_file() and "cache" not in p.parts]
results["upstream_tracked_status"] = command(["git", "-C", str(UPSTREAM), "status", "--porcelain", "--untracked-files=no"])
write(HERE / "results.json", results)
print(json.dumps({"results": str(HERE / "results.json"), "initial": results["initial"]["graph"],
                  "checks": {k: v["observed"] for k, v in results["checks"].items()}}, indent=2))

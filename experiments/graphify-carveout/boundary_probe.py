"""Focused follow-ups to negative observations; uses the first probe's saved graph."""
from __future__ import annotations

import copy
import asyncio
import importlib.metadata
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parents[1].parent / "graphify-upstream"
previous = json.loads((HERE / "results.json").read_text())
initial_graph = Path(previous["work_directory"]) / "initial-graph.json"
WORK = Path(tempfile.mkdtemp(prefix="boundary-", dir=HERE / "work"))
os.environ["GRAPHIFY_OUT"] = str(WORK / "graphify-out")
os.environ["GRAPHIFY_QUERY_LOG_DISABLE"] = "1"
os.environ["PYTHONPATH"] = os.pathsep.join([str(HERE / "offline"), str(UPSTREAM)])
sys.path.insert(0, str(UPSTREAM))
os.chdir(WORK)

import networkx as nx
from graphify.build import build_from_json, _is_ast_tier
from graphify.extract import extract, _get_extractor
from graphify.serve import _load_graph, _shortest_path_text, _build_http_app

results = {"upstream_sha": previous["upstream_sha"], "mcp_version": importlib.metadata.version("mcp")}
G = _load_graph(str(initial_graph))
src, dst = "runtime_app_run", "runtime_task_validate_request"
assert src in G and dst in G
results["path"] = {
    "exact_ids": [src, dst], "networkx": nx.shortest_path(G, src, dst),
    "graphify_text": _shortest_path_text(G, {"source": src, "target": dst}),
}

# Capture stderr to a file so startup diagnostics cannot block the child's pipe.
errfile = (WORK / "mcp.stderr").open("w")
server_args = ([sys.executable, "-u", str(HERE / "mcp_factory_server.py"), str(initial_graph)]
               if "--factory" in sys.argv else [sys.executable, "-u", "-m", "graphify.serve", str(initial_graph)])
results["mcp_invocation"] = server_args
proc = subprocess.Popen(server_args,
                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errfile)
messages = []
pending = b""


def rpc(method, params, id_):
    global pending
    proc.stdin.write((json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params}) + "\n").encode())
    proc.stdin.flush()
    until = time.monotonic() + 8
    while time.monotonic() < until:
        while b"\n" in pending:
            line, pending = pending.split(b"\n", 1)
            if not line.strip():
                continue
            response = json.loads(line)
            messages.append(response)
            if response.get("id") == id_:
                return response
        if not select.select([proc.stdout], [], [], max(0, until - time.monotonic()))[0]:
            break
        chunk = os.read(proc.stdout.fileno(), 65536)
        if not chunk:
            raise RuntimeError("MCP stdout closed")
        pending += chunk
    raise TimeoutError(method)


try:
    rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}}, 1)
    proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
    proc.stdin.flush()
    rpc("tools/list", {}, 2)
    rpc("tools/call", {"name": "graph_stats", "arguments": {}}, 3)
    rpc("tools/call", {"name": "get_node", "arguments": {"label": dst}}, 4)
    rpc("tools/call", {"name": "query_graph", "arguments": {"question": "validate_request", "token_budget": 500}}, 5)
    rpc("tools/call", {"name": "query_graph", "arguments": {"question": "validate_request", "depth": "invalid"}}, 6)
    rpc("resources/list", {}, 7)
except Exception as exc:
    results["mcp_error"] = repr(exc)
finally:
    proc.stdin.close()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.terminate()
        proc.wait(timeout=3)
    errfile.close()
    results["mcp_returncode"] = proc.returncode
    results["mcp_stderr"] = (WORK / "mcp.stderr").read_text()
    results["mcp_messages"] = messages

# Exercise Streamable HTTP's actual ASGI application in process; no listener.
async def http_control():
    app = _build_http_app(str(initial_graph), stateless=True, json_response=True)
    responses = []
    async with app.router.lifespan_context(app):
        for id_, method, params in [
            (1, "initialize", {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "probe", "version": "1"}}),
            (2, "tools/list", {}),
            (3, "tools/call", {"name": "get_node", "arguments": {"label": dst}}),
        ]:
            body = json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params}).encode()
            sent = False
            output = []
            async def receive():
                nonlocal sent
                if not sent:
                    sent = True
                    return {"type": "http.request", "body": body, "more_body": False}
                await asyncio.Event().wait()
            async def send(message):
                output.append(message)
            scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                     "method": "POST", "scheme": "http", "path": "/mcp", "raw_path": b"/mcp",
                     "query_string": b"", "root_path": "", "server": ("127.0.0.1", 8080), "client": ("127.0.0.1", 50000),
                     "headers": [(b"host", b"127.0.0.1:8080"), (b"content-type", b"application/json"),
                                 (b"accept", b"application/json, text/event-stream")]}
            await asyncio.wait_for(app(scope, receive, send), timeout=5)
            responses.append({"method": method, "status": next(m["status"] for m in output if m["type"] == "http.response.start"),
                              "body": b"".join(m.get("body", b"") for m in output).decode()})
    return responses

try:
    results["http_asgi"] = asyncio.run(http_control())
except Exception as exc:
    results["http_asgi_error"] = repr(exc)

if "--factory" in sys.argv:
    (HERE / "factory-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({k: v for k, v in results.items() if k not in {"mcp_messages", "http_asgi"}}, indent=2))
    sys.exit(0)

# Declared dependency edges to packages outside the corpus vs actual persisted graph.
fixtures = {
    "python/pyproject.toml": '[project]\nname="probe-python"\nversion="1.0"\ndependencies=["httpx>=0.27"]\n',
    "go/go.mod": 'module example.org/probe\n\ngo 1.23\nrequire example.org/external v1.2.3\n',
    "rust/Cargo.toml": '[package]\nname="probe-rust"\nversion="1.0.0"\n[dependencies]\nserde="1"\n',
    "java/pom.xml": '<project><groupId>example</groupId><artifactId>probe</artifactId><dependencies><dependency><groupId>example</groupId><artifactId>external</artifactId><version>1</version></dependency></dependencies></project>',
    "schema.sql": 'CREATE TABLE users (id INT PRIMARY KEY);\nCREATE TABLE orders (id INT PRIMARY KEY, user_id INT REFERENCES users(id));\nCREATE VIEW orders_view AS SELECT * FROM orders;\n',
    "config.yaml": 'server:\n  port: 8080\n',
    "config.toml": '[server]\nport=8080\n',
    "requirements.txt": 'httpx==0.27.0\n',
    "build.gradle": 'plugins { id "java" }\ndependencies { implementation "example:external:1.0" }\n',
    "Overloaded.java": 'class Overloaded { void run(int x) {} void run(String x) {} }\n',
}
paths = []
for path, body in fixtures.items():
    p = WORK / "fixtures" / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body)
    paths.append(p)
raw = extract(paths, root=WORK / "fixtures", cache_root=WORK, parallel=False)
graph = build_from_json(copy.deepcopy(raw), directed=True)
results["fixtures"] = {
    "inputs": fixtures,
    "extractor_available": {str(p.relative_to(WORK / "fixtures")): _get_extractor(p) is not None for p in paths},
    "raw": raw,
    "graph_nodes": [dict(id=n, **d) for n, d in graph.nodes(data=True)],
    "graph_edges": [dict(source=u, target=v, **d) for u, v, d in graph.edges(data=True)],
}

# Stub only the model transport. Exercise the unchanged semantic postprocessing.
# This supplies a synthetic response; it is NOT local-model quality evidence.
import graphify.llm as llm
captured = {}


def fake_chat(**kwargs):
    captured["request"] = kwargs
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({
        "nodes": [{"id": "model_claim", "label": "server", "file_type": "document", "source_file": "config.yaml", "source_location": "L1"}],
        "edges": [],
    })), finish_reason="stop")], usage=SimpleNamespace(prompt_tokens=10, completion_tokens=80))


def fake_client(**kwargs):
    captured["client"] = kwargs
    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fake_chat)))


sys.modules["openai"] = SimpleNamespace(OpenAI=fake_client)
sem = llm.extract_files_direct([WORK / "fixtures/config.yaml"], root=WORK / "fixtures", backend="ollama", model="qwen-probe-only")
captured["client"].pop("api_key", None)
results["synthetic_semantic_transport"] = {
    "synthetic_not_llm": True, "client": captured["client"],
    "request_keys": sorted(captured["request"]), "model": captured["request"]["model"],
    "extra_body": captured["request"].get("extra_body"), "returned": sem,
    "tier_classification_of_model_node": _is_ast_tier(sem["nodes"][0]),
    "tier_classification_with_null_location": _is_ast_tier({**sem["nodes"][0], "source_location": None}),
}
filename = "factory-results.json" if "--factory" in sys.argv else "boundary-results.json"
(HERE / filename).write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps({"mcp_error": results.get("mcp_error"), "mcp_messages": len(messages), "mcp_stderr": results["mcp_stderr"], "path": results["path"]}, indent=2))

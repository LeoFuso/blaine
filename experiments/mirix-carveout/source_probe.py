#!/usr/bin/env python3
"""Execute narrow, unchanged AST fragments from pinned MIRIX without importing it.

No server, database, SDK, model, network, or real credentials are used. This
checks source-level behavior, not integration or end-to-end compatibility.
"""
import ast
import asyncio
import copy
import inspect
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

SHA = "8cb06a62bbb7c478beb33dd4f2815696a72df482"
root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3] / "mirix-upstream"
head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
assert head == SHA, f"Expected {SHA}, found {head}"


def tree(path):
    return ast.parse((root / path).read_text())


def function(path, name):
    return copy.deepcopy(next(n for n in ast.walk(tree(path))
                              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name))


def load_function(path, name, bindings):
    node = function(path, name)
    node.decorator_list = []
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), node], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(root / path), "exec"), bindings)
    return bindings[name]


def run_statements(statements, bindings):
    exec(compile(ast.fix_missing_locations(ast.Module(body=copy.deepcopy(statements), type_ignores=[])), "<upstream-fragment>", "exec"), bindings)
    return bindings


def assigns(node, name):
    return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code, self.detail = status_code, detail


async def main():
    observations = {"upstream_sha": head, "kind": "isolated source-fragment execution; no integration test"}
    # An explicit synthetic key avoids environment/provider-database lookup.
    prepare = load_function("mirix/llm_api/openai_client.py", "_prepare_client_kwargs", {})
    config = SimpleNamespace(api_key="SYNTHETIC-NOT-A-CREDENTIAL", model_endpoint="http://127.0.0.1:8000/v1", auth_provider=None)
    kwargs = await prepare(SimpleNamespace(llm_config=config))
    assert kwargs == {"api_key": config.api_key, "base_url": config.model_endpoint}
    observations["openai_custom_endpoint"] = {"base_url": kwargs["base_url"], "explicit_synthetic_key_preserved": True}

    # This is the actual header resolver with a dummy server, no HTTP request.
    resolver = load_function("mirix/server/rest_api.py", "get_client_and_org", {
        "get_server": lambda: SimpleNamespace(organization_manager=SimpleNamespace(DEFAULT_ORG_ID="default-org")),
        "HTTPException": HTTPException,
    })
    identity = await resolver(x_client_id="caller-supplied-client", x_org_id="caller-supplied-org")
    assert identity == ("caller-supplied-client", "caller-supplied-org")
    try:
        await resolver()
        raise AssertionError("Missing headers unexpectedly accepted")
    except HTTPException as exc:
        assert exc.status_code == 401
    observations["identity_header_resolver"] = {"caller_ids_accepted_without_api_key": True, "no_headers_status": 401}

    # Run the real add/add_sync preprocessing up to (but not including) the
    # converter; assert both handlers contain the same preprocessing fragment.
    preprocess = []
    for name in ("add_memory", "add_memory_sync"):
        body = function("mirix/server/rest_api.py", name).body
        start = next(i for i, n in enumerate(body) if assigns(n, "message"))
        end = next(i for i, n in enumerate(body) if assigns(n, "input_messages"))
        preprocess.append(body[start:end])
    assert ast.dump(ast.Module(body=preprocess[0], type_ignores=[])) == ast.dump(ast.Module(body=preprocess[1], type_ignores=[]))
    cases = {
        "role_with_string": [{"role": "user", "content": "synthetic memory"}],
        "role_with_text_blocks": [{"role": "user", "content": [{"type": "text", "text": "synthetic memory"}]}],
        "flat_text_blocks": [{"type": "text", "text": "synthetic memory"}],
    }
    results = {}
    for label, messages in cases.items():
        try:
            result = run_statements(preprocess[0], {"request": SimpleNamespace(messages=messages)})
            results[label] = {"outcome": "accepted by preprocessing", "message": result["message"]}
        except TypeError as exc:
            results[label] = {"outcome": "TypeError", "error": str(exc)}
    assert results["role_with_text_blocks"]["outcome"] == "TypeError"
    assert results["role_with_string"]["outcome"] == "accepted by preprocessing"
    observations["add_preprocessing"] = results

    body = function("mirix/server/rest_api.py", "retrieve_memory_with_conversation").body
    start = next(i for i, n in enumerate(body) if assigns(n, "has_content"))
    guard_results = {}
    for label, messages in cases.items():
        result = run_statements(body[start:start + 2], {"request": SimpleNamespace(messages=messages)})
        guard_results[label] = result["has_content"]
    assert guard_results == {"role_with_string": False, "role_with_text_blocks": True, "flat_text_blocks": False}
    # The shape that passes the guard fails in the topic extractor's own
    # conversion, before any model call. Execute that exact if-statement.
    extractor = function("mirix/server/rest_api.py", "extract_topics_and_temporal_info")
    conversion = next(n for n in extractor.body if isinstance(n, ast.Try)).body[0]
    try:
        run_statements([conversion], {"messages": cases["role_with_text_blocks"]})
        raise AssertionError("Expected topic conversion TypeError")
    except TypeError:
        pass
    observations["conversational_retrieval"] = {"has_content_guard": guard_results, "text_blocks_topic_conversion": "TypeError (caught by the full upstream extractor, which returns no topics)"}

    factory = function("mirix/llm_api/llm_client.py", "create")
    match = next(n for n in factory.body if isinstance(n, ast.Match))
    cases_in_factory = [c.pattern.value.value for c in match.cases if isinstance(c.pattern, ast.MatchValue)]
    assert not (root / "mirix/llm_api/openrouter_client.py").exists()
    observations["llm_factory"] = {"explicit_cases": cases_in_factory, "openrouter_client_file_exists": False}
    fallback = load_function("mirix/llm_api/llm_api_tools.py", "create", {})
    ai_reply = function("mirix/agent/agent.py", "_get_ai_reply")
    fallback_call = next(n for n in ast.walk(ai_reply)
                         if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "create")
    assert "user_id" in [kw.arg for kw in fallback_call.keywords]
    try:
        inspect.signature(fallback).bind(llm_config=None, messages=[], user_id="synthetic")
        raise AssertionError("Expected fallback signature mismatch")
    except TypeError as exc:
        observations["agent_legacy_fallback"] = {"signature_binding": "TypeError", "error": str(exc)}
    sdk_add = function("mirix/client/remote_client.py", "add")
    assert "session_tag" not in [a.arg for a in sdk_add.args.args]
    observations["sdk_add_exposes_session_tag"] = False
    print(json.dumps(observations, indent=2))


asyncio.run(main())

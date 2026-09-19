"""Read-only inventory probe. No environment dumps, secrets or service mutations."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from urllib.error import HTTPError
from urllib.request import build_opener, ProxyHandler, Request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def command(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=8)
        return {"exit": r.returncode, "stdout": r.stdout.strip(), "stderr": r.stderr.strip()}
    except Exception as e:
        return {"error_type": type(e).__name__}


result = {"commands": {x: shutil.which(x) for x in
          ["devenv", "nix", "process-compose", "secretspec", "bws", "uv", "pg_isready", "redis-cli"]}}
paths = [ROOT / ".local/bin/restate-server", ROOT / ".local/runtime-venv/bin/python",
         Path.home() / "workspace/vllm-lab/.venv/bin/vllm",
         Path.home() / "workspace/mirix/.venv/bin/mirix",
         Path("/nix/var/nix/profiles/default/bin/nix"), Path.home() / ".nix-profile/bin/nix"]
result["executables"] = {str(p): os.access(p, os.X_OK) for p in paths}
result["postgres"] = command(["pg_isready", "-h", "127.0.0.1", "-p", "5432"])
result["redis"] = command(["redis-cli", "-h", "127.0.0.1", "-p", "6379", "PING"])
result["bws_version"] = command(["bws", "--version"])
result["http"] = {}
for name, url, headers in [
    ("qwen", "http://127.0.0.1:8000/health", {}),
    ("bge", "http://127.0.0.1:8001/health", {}),
    ("mirix", "http://127.0.0.1:8531/health", {}),
    ("restate", "http://127.0.0.1:29070/deployments", {}),
    ("runtime", "http://127.0.0.1:29080/discover", {"Accept": "application/vnd.restate.endpointmanifest.v2+json"}),
]:
    try:
        with build_opener(ProxyHandler({})).open(Request(url, headers=headers), timeout=3) as r:
            result["http"][name] = {"url": url, "status": r.status}
    except HTTPError as e:
        result["http"][name] = {"url": url, "status": e.code}
    except Exception as e:
        result["http"][name] = {"url": url, "error_type": type(e).__name__}

# Only known non-secret launch options; never dump process argv or environ.
flags = {"--host", "--port", "--model", "--max-model-len", "--gpu-memory-utilization",
         "--reasoning-parser", "--tool-call-parser", "--runner", "--convert"}
result["launch_options"] = []
for path in Path("/proc").glob("[0-9]*/cmdline"):
    try:
        args = path.read_bytes().decode().split("\0")
        if not any(a.endswith("/bin/vllm") or a.endswith("/bin/mirix") or a == "mirix.server.rest_api.app" for a in args):
            continue
        safe = {args[i]: args[i+1] for i in range(len(args)-1) if args[i] in flags}
        safe["kind"] = "vllm" if any(a.endswith("/bin/vllm") for a in args) else "mirix"
        safe["enable_auto_tool_choice"] = "--enable-auto-tool-choice" in args
        if "serve" in args:
            i = args.index("serve")
            if i+1 < len(args) and args[i+1] in {"Qwen/Qwen3.5-9B", "BAAI/bge-m3"}:
                safe["served_model"] = args[i+1]
        result["launch_options"].append(safe)
    except (OSError, UnicodeError):
        continue

(HERE / "host-observations.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))

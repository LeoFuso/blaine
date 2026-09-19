# Static prototype for current devenv 2.3 syntax; NOT evaluated or started.
{ config, ... }:
let
  workspace = "/home/leofuso/workspace";
  blaine = "${config.devenv.root}/../..";
  vllm = "${workspace}/vllm-lab/.venv/bin/vllm";
  mirixPython = "${workspace}/mirix/.venv/bin/python";
  runtimePython = "${blaine}/.local/runtime-venv/bin/python";
in
{
  # No Python/CUDA/driver/database migration into Nix.
  packages = [ ];

  tasks."native:ready".exec = ''
    set -e
    /usr/bin/pg_isready -h 127.0.0.1 -p 5432
    test "$(/usr/bin/redis-cli -h 127.0.0.1 -p 6379 --raw PING)" = PONG
  '';

  processes.qwen = {
    cwd = "${workspace}/vllm-lab";
    exec = ''
      exec "${vllm}" serve Qwen/Qwen3.5-9B \
        --host 127.0.0.1 --port 8000 --max-model-len 32768 \
        --gpu-memory-utilization 0.80 \
        --enable-auto-tool-choice --tool-call-parser qwen3_xml \
        --reasoning-parser qwen3
    '';
    ready = {
      http.get = { port = 8000; path = "/health"; };
      period = 5;
      timeout = 600;
    };
    restart = { on = "on_failure"; max = 2; };
    shutdown.grace = 30;
  };

  processes.bge = {
    cwd = "${workspace}/vllm-lab";
    exec = ''
      exec "${vllm}" serve BAAI/bge-m3 \
        --host 127.0.0.1 --port 8001 --runner pooling \
        --gpu-memory-utilization 0.10
    '';
    ready = {
      http.get = { port = 8001; path = "/health"; };
      period = 5;
      timeout = 600;
    };
    restart = { on = "on_failure"; max = 2; };
    shutdown.grace = 30;
  };

  processes.mirix = {
    cwd = "${workspace}/mirix";
    after = [ "native:ready" "devenv:processes:qwen" "devenv:processes:bge" ];
    # Preserve the already-persisted Meta Agent / model configuration.
    env.MIRIX_REDIS_ENABLED = "true";
    env.SECRETSPEC_BWS_CLI_PATH = "/usr/local/bin/bws";
    exec = ''
      exec secretspec --file "${config.devenv.root}/secretspec.toml" \
        run --profile default --scope mirix -- \
        "${mirixPython}" -m uvicorn mirix.server.rest_api:app \
        --host 127.0.0.1 --port 8531
    '';
    ready = {
      http.get = { port = 8531; path = "/health"; };
      timeout = 120;
    };
    restart = { on = "on_failure"; max = 2; };
    shutdown.grace = 30;
  };

  processes.restate = {
    cwd = blaine;
    # Match dev.py's rejection of inherited RESTATE_* overrides without logging them.
    exec = ''
      for name in ''${!RESTATE_@}; do unset "$name"; done
      exec "${blaine}/.local/bin/restate-server" \
        --config-file runtime/interactive-restate.toml
    '';
    ready = {
      http.get = { port = 29070; path = "/deployments"; };
      timeout = 60;
    };
    restart = { on = "on_failure"; max = 2; };
    shutdown.grace = 10;
  };

  processes.blaine-runtime = {
    cwd = blaine;
    after = [ "devenv:processes:restate" ];
    exec = ''
      for name in ''${!RESTATE_@}; do unset "$name"; done
      exec "${runtimePython}" -m runtime.interactive
    '';
    ready = {
      exec = ''/usr/bin/curl --noproxy '*' --fail --silent --output /dev/null --max-time 2 -H 'Accept: application/vnd.restate.endpointmanifest.v2+json' http://127.0.0.1:29080/discover'';
      timeout = 60;
    };
    restart = { on = "on_failure"; max = 2; };
    shutdown.grace = 10;
  };

  # Reuse Blaine-specific registration helpers; do not invoke dev.py up/down.
  # This downstream task requires `up --mode all`, or explicit tasks run.
  tasks."blaine:register" = {
    after = [ "devenv:processes:restate" "devenv:processes:blaine-runtime" ];
    exec = ''
      cd "${blaine}"
      "${runtimePython}" - <<'PY'
      from scripts.dev import ENDPOINTS, RUNTIME_URI, http
      deployments = http(ENDPOINTS["admin"], "/deployments")
      if not any(d.get("uri") == RUNTIME_URI for d in deployments.get("deployments", [])):
          http(ENDPOINTS["admin"], "/deployments", {"uri": RUNTIME_URI})
      PY
    '';
  };
}

#!/usr/bin/env python3
"""Real Goose default-provider and existing Blaine worker-adapter acceptance."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.kernel.contracts import message
from runtime.kernel.worker import GooseWorker

out = ROOT / 'experiments/d1-service-adoption/evidence'
config = json.loads((ROOT / 'infra/inference/candidate.json').read_text())
env = {k:v for k,v in os.environ.items() if k in ['HOME','PATH','USER','LANG']}
env.update(GOOSE_DISABLE_KEYRING='true', GOOSE_TELEMETRY_ENABLED='false', OPENAI_API_KEY='EMPTY')
prompt = ('Read this actual local inference configuration. Explain the generation and embedding roles, '
          'their model names, and their context limits in a concise operational note. Do not call tools.\n'
          + json.dumps({k:config[k] for k in ['generation','embedding']}))
r = subprocess.run([str(Path.home()/'.local/bin/goose'), 'run', '--no-profile', '--no-session',
                    '--max-turns', '1', '--quiet', '--text', prompt],
                   env=env, capture_output=True, text=True, timeout=120, cwd=ROOT)
evidence = {'exit_code':r.returncode,'public_output':r.stdout,'stderr_bytes':len(r.stderr.encode()),
            'provider_model_override':False,'input':'actual candidate.json generation/embedding entries',
            'goose_version':subprocess.check_output([str(Path.home()/'.local/bin/goose'),'--version'],text=True).strip()}
(out/'goose-interaction.json').write_text(json.dumps(evidence,indent=2)+'\n')
assert r.returncode == 0 and all(s in r.stdout for s in ['Qwen3.8','bge-m3']), 'Goose default provider acceptance failed'
source = (ROOT/'runtime/personal_runtime.py').read_text()
packet = message('WorkerInput', {'task_id':'d1-worker-acceptance',
    'objective':'Read the supplied Python code. Which function raises TerminalError when no deterministic continuation exists? Return only its exact function name, without formatting.',
    'context':[{'source':'runtime/personal_runtime.py','content':source[:2048]}]})
worker = GooseWorker(Path.home()/'.local/bin/goose', Path.home()/'.local/share/blaine/runtime/worker-acceptance',
                     model=config['generation']['repository'])
result = worker(packet, 'd1-worker-acceptance/1')
(out/'worker-interaction.json').write_text(json.dumps({'result':result,'packet':packet,
    'worker_completion_is_not_task_completion':True},indent=2)+'\n')
assert result['outcome']=='success' and result['content']=='no_unnecessary_cognition', 'Worker adapter acceptance failed'
print('PASS: normal Goose provider and real Blaine GooseWorker adapter')

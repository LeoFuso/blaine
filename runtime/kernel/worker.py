"""Bounded text-only worker seam. A worker result is not Task completion."""
from dataclasses import dataclass
from pathlib import Path
import os
import subprocess
import tempfile
import uuid
from runtime.kernel.contracts import encode, fields, identifier, text, unpack


def validate_packet(raw, task_id):
    packet = fields(unpack(raw, 'WorkerInput'), {'task_id', 'objective', 'context'})
    if packet['task_id'] != task_id:
        raise ValueError('Worker packet Task mismatch')
    text(packet['objective'], 1024)
    if not isinstance(packet['context'], list) or len(packet['context']) > 4:
        raise ValueError('Worker context must be selected and bounded')
    for item in packet['context']:
        fields(item, {'source', 'content'})
        text(item['source'], 256)
        text(item['content'], 2048)
    if len(encode(raw)) > 4096:
        raise ValueError('Worker packet exceeds budget')
    return packet


@dataclass
class GooseWorker:
    """No profile, tools, inherited session or Task-state handles. Local inference only."""
    executable: Path
    root: Path
    audit: object = None
    proxy: str | None = None
    started: object = None  # trusted deployment observer; never selected by cognition

    def __call__(self, packet, operation_id):
        validate_packet(packet, packet['payload']['task_id'])
        attempt = 'worker-' + uuid.uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=attempt+'-', dir=self.root) as directory:
            env = {k:v for k,v in os.environ.items() if k in ('PATH','HOME','USER','LANG','TMPDIR')}
            settings = {'GOOSE_PATH_ROOT': directory+'/goose', 'GOOSE_DISABLE_KEYRING':'true',
                'GOOSE_TELEMETRY_ENABLED':'false', 'OPENAI_HOST':'http://127.0.0.1:8000',
                'OPENAI_API_KEY':'EMPTY'}
            if self.proxy:
                for key in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):
                    settings[key] = self.proxy
                settings.update(NO_PROXY='', no_proxy='')
            env.update(settings)
            command = [str(self.executable), 'run', '--no-profile', '--no-session', '--provider', 'openai',
                       '--model', 'Qwen/Qwen3.5-9B', '--max-turns', '1', '--quiet', '--instructions', '-']
            prompt = ('Execute only this bounded WorkerInput. You have no Task authority. '
                      'Use only supplied context. Return only the requested result, no reasoning or tools.\n' + encode(packet).decode())
            process = subprocess.Popen(command, cwd=directory, env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if self.started:
                self.started({'attempt_id':attempt,'pid':process.pid,'operation_id':operation_id})
            try:
                stdout, stderr = process.communicate(prompt.encode(), timeout=60)
            except subprocess.TimeoutExpired:
                process.kill(); stdout, stderr = process.communicate(timeout=5)
            outcome = 'success' if process.returncode == 0 else 'interrupted' if process.returncode < 0 else 'failure'
            if len(stdout) > 4096 or b'<think>' in stdout:
                outcome = 'failure'; public = ''
            else:
                public = stdout.decode('utf-8', errors='strict')
            result = {'attempt_id':attempt, 'operation_id':operation_id, 'outcome':outcome,
                      'exit_code':process.returncode, 'content':public.strip() if outcome=='success' else '',
                      'normalization':'strip terminal whitespace; raw public stdout retained in worker evidence',
                      'public_stdout':public, 'stderr_bytes':len(stderr)}
            if self.audit:
                self.audit({'packet':packet, 'packet_bytes':len(encode(packet)), 'command':command,
                            'cwd':directory, 'environment_overrides':settings, 'result':result})
            return result

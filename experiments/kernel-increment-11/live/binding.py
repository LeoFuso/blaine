"""One-shot experimental Codex binding. No runtime authority and no raw context."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from runtime.kernel.contracts import encode, fields, text

EXECUTABLE=Path('/home/leofuso/.codex/packages/standalone/releases/0.155.1-x86_64-unknown-linux-musl/bin/codex')
AUTH=Path('/home/leofuso/.codex/auth.json')  # mounted, never read by Blaine
CONFIG=Path(__file__).resolve().parent


def command():
    # Empty root, read-only system/program/config mounts; no host repo, personal
    # instructions, plugin configuration, memories or user documents are mounted.
    args=['/usr/bin/bwrap','--unshare-pid','--die-with-parent','--new-session',
        '--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
        '--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/probe','--chdir','/probe',
        '--dir','/home/leofuso/.codex','--ro-bind',str(AUTH),'/home/leofuso/.codex/auth.json',
        '--ro-bind',str(EXECUTABLE),'/codex',
        '--ro-bind',str(CONFIG/'config.toml'),'/home/leofuso/.codex/config.toml',
        '--ro-bind',str(CONFIG/'instructions.txt'),'/instructions.txt',
        '--ro-bind',str(CONFIG/'result.schema.json'),'/result.schema.json']
    for path in ('/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf','/etc/ssl/certs'):
        if Path(path).exists():args+=['--ro-bind',path,path]
    return args+['/codex','exec','--model','gpt-6-astra','--sandbox','read-only','--skip-git-repo-check',
                 '--ephemeral','--json','--output-schema','/result.schema.json','-']


def normalize(value):
    def unique(pairs):
        result={}
        for k,v in pairs:
            if k in result:raise ValueError('Duplicate output field')
            result[k]=v
        return result
    result=fields(json.loads(value,object_pairs_hook=unique),{'organization','marker'})
    for item in result.values():text(item,80)
    return encode(result).decode()  # serialization only, no value repair/injection


def claim_dispatch(path, request):
    """Adapter effect receipt, not a Task ledger. Unknown outcomes stay spent."""
    with path.open('xb',buffering=0) as f:
        f.write(encode({'worker_dispatch_id':request.worker_dispatch_id,'context_digest':request.context_digest,
                        'started_at_unix':time.time()}));os.fsync(f.fileno())
    directory=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(directory)
    finally:os.close(directory)


def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)


class CodexBinding:
    def __init__(self, output):self.output=output

    def dispatch(self, request):
        out=self.output
        # These constraints pin this concrete experimental adapter, independently
        # of model output. No other executable/model/provider is selectable here.
        assert request.binding.worker_family=='codex-cli-0.155.1'
        assert request.binding.provider=='openai-chatgpt'
        assert request.binding.model=='gpt-6-astra'
        assert request.binding.destination=='https://chatgpt.com'
        assert request.read_scope==('projected-context',) and request.write_scope==()
        assert request.runtime_ms<=60000
        assert hashlib.sha256(request.context.content.encode()).hexdigest()==request.context_digest
        if (out/'cancel-worker').exists():raise RuntimeError('Cancelled before launch')
        # Written/fsynced before Popen; never cleared. Even unjournaled response loss
        # cannot cause a second live launch. No automatic recovery of an unknown call.
        claim_dispatch(out/'worker-dispatch-started.json',request)
        (out/'authorized-worker-request.json').write_bytes(encode(asdict(request)))
        payload=request.context.content.encode('utf-8')
        (out/'worker-input.txt').write_bytes(payload)
        argv=command();(out/'worker-command.json').write_bytes(encode(argv))
        environment={'HOME':os.environ['HOME'],'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
        begin=time.monotonic();process=None;timed_out=False;cancelled=False
        stdout=b'';stderr=b''
        try:
            process=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env=environment,start_new_session=True)
            first=True
            while True:
                remaining=min(request.runtime_ms/1000-(time.monotonic()-begin),request.deadline_unix-time.time())
                if remaining<=0 or (out/'cancel-worker').exists():
                    timed_out=remaining<=0;cancelled=not timed_out;stop_process(process)
                    stdout,stderr=process.communicate(timeout=3);break
                try:
                    stdout,stderr=process.communicate(payload if first else None,timeout=min(1,remaining));break
                except subprocess.TimeoutExpired:first=False
        finally:
            if process is not None:stop_process(process)
        # Persist only public results/session/usage events. No private reasoning,
        # full provider requests, environment objects or credential-bearing stderr.
        public=[];messages=[];session=None;usage={};unexpected=[]
        for line in stdout.splitlines():
            try:event=json.loads(line)
            except ValueError:unexpected.append('non_json_cli_output');continue
            kind=event.get('type')
            if kind=='thread.started':
                session=event.get('thread_id');public.append({'type':kind,'thread_id':session})
            elif kind=='turn.completed':
                raw=event.get('usage',{})
                usage={k:raw[k] for k in ('input_tokens','output_tokens','cached_input_tokens') if type(raw.get(k)) is int}
                public.append({'type':kind,'usage':usage})
            elif kind=='item.completed':
                item=event.get('item',{})
                if item.get('type')=='agent_message':
                    content=text(item.get('text'),2048);messages.append(content)
                    public.append({'type':kind,'item':{'type':'agent_message','text':content}})
                elif item.get('type') not in ('reasoning',):unexpected.append('unrequested_item:'+str(item.get('type')))
            elif kind in ('error','turn.failed'):public.append({'type':kind,'detail':'not retained; provider error'})
        observation={'worker_dispatch_id':request.worker_dispatch_id,'worker_session_id':session,
            'exit_code':process.returncode,'timed_out':timed_out,'cancelled':cancelled,
            'runtime_ms':int((time.monotonic()-begin)*1000),'worker_dispatch_count':1,
            'provider':'openai-chatgpt','model_intent':'gpt-6-astra','resolved_model':None,'resolved_account':None,
            'trust_boundary':'https://chatgpt.com','final_provider_prompt':None,
            'model_call_count':None,'provider_internal_retry_count':None,'monetary_cost':None,
            'usage':usage,'events':public,'unexpected_items':unexpected,'stderr_bytes':len(stderr),
            'context_digest':request.context_digest,'context_boundary':'exact stdin bytes from authorized projection'}
        (out/'worker-observation.json').write_bytes(encode(observation))
        if process.returncode!=0 or timed_out or cancelled or unexpected or len(messages)!=1 or not session:
            raise RuntimeError('Single worker dispatch did not produce an unambiguous result')
        result={'status':'executed','content':normalize(messages[0]),'worker_session_id':session,
            'producer':{k:getattr(request.binding,k) for k in ('worker_family','provider','model','destination')},
            'usage':{k:usage[k] for k in ('input_tokens','output_tokens') if k in usage}}
        (out/'worker-normalized-result.json').write_bytes(encode(result))
        return result

"""One-shot experimental Codex binding. No runtime authority and no raw context."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from runtime.kernel.contracts import encode, fields, text

EXECUTABLE=Path('/home/leofuso/.codex/packages/standalone/releases/0.155.1-x86_64-unknown-linux-musl/bin/codex')
AUTH=Path('/home/leofuso/.codex/auth.json')  # mounted, never read by Blaine
CONFIG=Path(__file__).resolve().parent
PROTOCOL = 'codex-exec/rust-v0.155.1'
PROTOCOL_SOURCE = 'https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/exec/src/exec_events.rs'


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON field')
        result[key] = value
    return result


def diagnostic_message(value):
    """Closed structural representation, never arbitrary provider diagnostic text.

    Redacting *all* free text avoids pretending a token/PII regex can make it safe.
    No raw prefix, hash, exception string or extra provider fields are persisted.
    """
    return {'present': isinstance(value, str),
            'utf8_bytes': len(value.encode('utf-8', errors='replace')) if isinstance(value, str) else None,
            'representation': '[untrusted diagnostic text omitted]',
            'retention': 'structure_only'}


def observe_stream(stdout, *, exit_code, timed_out=False, cancelled=False):
    """One-turn Codex 0.155.1 translation; no Task/lifecycle authority.

    Returns a safe observation and (only on success) normalized candidate content.
    Conflicting/duplicate terminal markers are not resolved optimistically.
    """
    events, diagnostics, reasons, messages, terminals = [], [], [], [], []
    session, usage = None, {}
    turn_started = False
    known = {'thread.started', 'turn.started', 'turn.completed', 'turn.failed',
             'error', 'item.started', 'item.updated', 'item.completed'}
    lines = stdout.splitlines()
    if len(stdout) > 262144 or len(lines) > 128:
        reasons.append('stream_limit_exceeded')
        lines = []
    for sequence, line in enumerate(lines, 1):
        record = {'sequence': sequence, 'type': 'unknown', 'classification': 'unknown',
                  'classification_source': PROTOCOL}
        events.append(record)
        try:
            if len(line) > 32768:
                raise ValueError('Event limit')
            event = json.loads(line, object_pairs_hook=unique)
            if not isinstance(event, dict) or not isinstance(event.get('type'), str):
                raise ValueError('Event object required')
            kind = event['type']
            if kind not in known:
                reasons.append('unknown_event')
                continue  # Do not persist an untrusted discriminator string.
            record['type'] = kind
            if terminals and kind not in ('turn.completed', 'turn.failed', 'error'):
                reasons.append('event_after_terminal')
            if kind == 'thread.started':
                identity = event.get('thread_id')
                if session is not None or sequence != 1 or not isinstance(identity, str) or not re.fullmatch(
                        r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', identity):
                    raise ValueError('Invalid session identity')
                session = identity
                record.update(thread_id=session, classification='session')
            elif kind == 'turn.started':
                if turn_started:
                    reasons.append('multiple_turns')
                turn_started = True
                record['classification'] = 'progress'
            elif kind == 'turn.completed':
                terminals.append('success')
                raw = event.get('usage')
                if not isinstance(raw, dict):
                    raise ValueError('Usage object required')
                for key in ('input_tokens', 'output_tokens', 'cached_input_tokens'):
                    if type(raw.get(key)) is not int or raw[key] < 0:
                        raise ValueError('Invalid usage')
                usage = {k: raw[k] for k in ('input_tokens', 'output_tokens', 'cached_input_tokens')}
                record.update(classification='terminal_success', usage=usage)
            elif kind in ('turn.failed', 'error'):
                terminals.append('failure')
                detail = event.get('error') if kind == 'turn.failed' else event
                if not isinstance(detail, dict) or not isinstance(detail.get('message'), str):
                    raise ValueError('Error message required')
                record.update(classification='terminal_failure', message=diagnostic_message(detail['message']))
                diagnostics.append(record.copy())
            else:
                item = event.get('item')
                if not isinstance(item, dict):
                    raise ValueError('Item object required')
                item_type = item.get('type')
                if item_type not in ('agent_message', 'reasoning', 'error'):
                    reasons.append('unrequested_item')
                    continue  # Tools/effects remain outside this binding's scope.
                record['item_type'] = item_type
                identity = item.get('id')
                record['item_id'] = identity if isinstance(identity, str) and re.fullmatch(r'item_[0-9]{1,10}', identity) else None
                record['item_id_retention'] = 'protocol_shape' if record['item_id'] else 'absent_or_omitted'
                if item_type == 'error':
                    if not isinstance(item.get('message'), str):
                        raise ValueError('Error message required')
                    record.update(classification='non_terminal_diagnostic', terminal=False,
                                  message=diagnostic_message(item['message']), classification_source=PROTOCOL)
                    diagnostics.append(record.copy())
                elif item_type == 'reasoning':
                    record['classification'] = 'private_content_omitted'
                else:
                    record['classification'] = 'result_content' if kind == 'item.completed' else 'streamed_content_omitted'
                    if kind == 'item.completed':
                        messages.append(text(item.get('text'), 2048))
                    # Raw model text is not copied into observation telemetry.
        except (ValueError, TypeError, UnicodeError, RecursionError):
            record['classification'] = 'malformed'
            reasons.append('malformed_event')
    terminal = ('conflicting' if len(terminals) > 1 else terminals[0] if terminals else 'missing')
    if terminal != 'success':
        reasons.append('terminal_' + terminal)
    if not session:
        reasons.append('missing_session')
    if len(messages) != 1:
        reasons.append('result_count')
    if timed_out or cancelled:
        reasons.append('timeout' if timed_out else 'cancelled')
    if exit_code != 0:
        reasons.append('process_exit')
    content = None
    if len(messages) == 1:
        try:
            content = normalize(messages[0])
        except (ValueError, TypeError, UnicodeError, RecursionError):
            reasons.append('invalid_result_contract')
    outcome = ('success' if not reasons else 'failure' if terminal == 'failure' or
               (exit_code != 0 and not timed_out and not cancelled) else 'unknown')
    if reasons:
        content = None
    return {'protocol': PROTOCOL, 'protocol_source': PROTOCOL_SOURCE,
            'terminal_status': terminal, 'normalized_outcome': outcome,
            'rejection_reasons': sorted(set(reasons)), 'result_present': bool(messages),
            'events': events, 'diagnostics': diagnostics, 'worker_session_id': session,
            'usage': usage}, content


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
        stream, content = observe_stream(stdout, exit_code=process.returncode,
                                         timed_out=timed_out, cancelled=cancelled)
        session, usage = stream['worker_session_id'], stream['usage']
        observation={'observation_version':2,'worker_dispatch_id':request.worker_dispatch_id,'worker_session_id':session,
            'exit_code':process.returncode,'timed_out':timed_out,'cancelled':cancelled,
            'runtime_ms':int((time.monotonic()-begin)*1000),'worker_dispatch_count':1,
            'provider':'openai-chatgpt','model_intent':'gpt-6-astra','resolved_model':None,'resolved_account':None,
            'trust_boundary':'https://chatgpt.com','final_provider_prompt':None,
            'model_call_count':None,'provider_internal_retry_count':None,'monetary_cost':None,
            'usage':usage,'events':stream['events'],'unexpected_items':stream['rejection_reasons'],
            'protocol':stream['protocol'],'protocol_source':stream['protocol_source'],
            'terminal_status':stream['terminal_status'],'normalized_outcome':stream['normalized_outcome'],
            'result_present':stream['result_present'],'diagnostics':stream['diagnostics'],
            'rejection_reasons':stream['rejection_reasons'],'stderr_bytes':len(stderr),
            'context_digest':request.context_digest,'context_boundary':'exact stdin bytes from authorized projection'}
        (out/'worker-observation.json').write_bytes(encode(observation))
        if stream['normalized_outcome'] != 'success':
            raise RuntimeError('Single worker dispatch did not produce an unambiguous result')
        result={'status':'executed','content':content,'worker_session_id':session,
            'producer':{k:getattr(request.binding,k) for k in ('worker_family','provider','model','destination')},
            'usage':{k:usage[k] for k in ('input_tokens','output_tokens') if k in usage}}
        (out/'worker-normalized-result.json').write_bytes(encode(result))
        return result

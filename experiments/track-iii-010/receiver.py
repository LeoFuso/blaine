"""Offline receiver only. State files/route/role are harness-owned, never RPC inputs.

References are not credentials. This is not an authentication system or a sandbox
against code that can edit the trusted fixture. No production interfaces are defined.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'track-iii-002'))
from evaluator import ContextTree, Rejected

PAIRS = {('USER_DECLARATION', 'DECLARED'), ('AGENT_OBSERVATION', 'UNVERIFIED'),
         ('VERIFIED_OUTCOME', 'VERIFIED_SUCCESS'), ('VERIFIED_OUTCOME', 'VERIFIED_FAILURE')}
DOMAINS = {'public', 'personal', 'employer-x'}
BOUND = 2048


def wire(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate field')
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def result(status, envelope=None, context=None):
    return dict(status=status, entries=[], partial=False,
                receipt=None if context is None else dict(context_id=context,
                    trace_id=envelope['trace_id'], parent_operation_id=envelope['parent_operation_id']),
                diagnostic={'code': status})


def packed(entries, envelope, context):
    out = result('SUCCESS' if entries else 'EMPTY', envelope, context)
    out['partial'] = False  # Reserve longer 'false'; final 'true' can only shrink.
    omitted = False
    for row in sorted(entries, key=lambda r: r['id']):
        trial = copy.deepcopy(out)
        trial['entries'].append(row)
        if len((wire(trial) + '\n').encode()) <= BOUND:
            out = trial
        else:
            omitted = True
    out['partial'] = omitted
    return out


def receive(raw, state, participant='worker', route='execution-main', mutation=None):
    """Reconstruct on EVERY operation. Mutation selector is trusted test harness only."""
    try:
        e = parse(raw)
        required = {'execution_id', 'context_id', 'binding_ref', 'policy_ref',
                    'topology_ref', 'trace_id', 'parent_operation_id', 'claims'}
        if (not isinstance(e, dict) or set(e) != required or not isinstance(e['claims'], dict)
                or any(not isinstance(e[k], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', e[k])
                       for k in required - {'claims'})):
            return result('INVALID_CONTEXT')
        # Current trusted state is loaded independently of this envelope.
        if state.get('policy') is None or state.get('current_evidence') is None:
            return result('UNAVAILABLE')
        if (e['policy_ref'] not in state['known_policy_refs']
                or e['topology_ref'] not in state['known_topology_refs']
                or state['policy_revision'] not in state['known_policy_refs']
                or state['topology_revision'] not in state['known_topology_refs']):
            return result('INVALID_CONTEXT')
        b = state['bindings'].get(route)
        if b is None:
            return result('UNAVAILABLE')
        if (e['execution_id'] != route or e['context_id'] != b['context_id']
                or e['binding_ref'] != b['binding_ref'] or participant not in b['participants']):
            return result('DENIED')
        if state['current_evidence'].get(b['required_evidence']) != {
                'binding_ref': b['binding_ref'], 'status': 'VALID'}:
            return result('UNAVAILABLE')
        # Whole-tree structural validation, including forbidden branches.
        tree = ContextTree(state['nodes'], [dict(id=r['id'], context_id=r['context_id'],
                                               content=r['content']) for r in state['entries']])
        token = tree.bind(b['context_id'])
        domains = state['context_domains']
        if (set(domains) != {n['id'] for n in state['nodes']} or
                not set(domains.values()) <= DOMAINS or domains[b['context_id']] != b['domain']):
            return result('INVALID_CONTEXT')
        rows = state['entries']
        if any(set(r) != {'id','context_id','domain','content','provenance','semantic_status'} or
               r['domain'] not in DOMAINS or (r['provenance'],r['semantic_status']) not in PAIRS
               for r in rows):
            return result('INVALID_CONTEXT')
        policy = state['policy']
        if (not isinstance(policy, dict) or set(policy) != {'grants','deny_ids'} or
                set(policy['grants']) != DOMAINS or
                any(not isinstance(v,list) or not set(v) <= {d,'public'} or len(v) != len(set(v))
                    for d,v in policy['grants'].items()) or
                not isinstance(policy['deny_ids'],list) or
                not set(policy['deny_ids']) <= {r['id'] for r in rows}):
            return result('INVALID_CONTEXT')
        if mutation == 'stale-policy':
            policy = e['claims'].get('policy_snapshot', policy)
        lineage = tree._lineage(b['context_id'])
        scopes = e['claims'].get('readable_scopes') if mutation == 'serialized-scope' else None
        def allowed(r):
            if scopes is not None:
                return r['context_id'] in scopes  # isolated unsafe control
            return (r['context_id'] in lineage and r['domain'] in policy['grants'][b['domain']]
                    and r['id'] not in policy['deny_ids'])
        request = e['claims'].get('request', {'op':'search', 'query':''})
        if not isinstance(request,dict):
            return result('DENIED')
        shapes = {'search':{'op','query'}, 'get':{'op','id'},
                  'recordObservation':{'op','id','content'}}
        if request.get('op') not in shapes or set(request) != shapes[request['op']] or any(
                not isinstance(v,str) for v in request.values()):
            return result('DENIED')
        if request['op'] == 'recordObservation':
            if participant not in {'cognition','worker'} or not re.fullmatch(r'[a-z0-9-]{1,24}',request['id']):
                return result('DENIED')
            scoped_id = b['context_id'] + '::' + request['id']
            if any(r['id'] == scoped_id for r in rows):
                return result('DENIED')
            row = dict(id=scoped_id, context_id=b['context_id'], domain=b['domain'],
                       content=request['content'], provenance='AGENT_OBSERVATION', semantic_status='UNVERIFIED')
            # Original III.2 closed write API enforces current-context ownership too.
            tree.handle(token, {'op':'write','entry_id':scoped_id,'content':row['content']})
            rows.append(row)
            selected = [row]
        else:
            selected = [copy.deepcopy(r) for r in rows if allowed(r) and (
                request['id'] == r['id'] if request['op'] == 'get'
                else request['query'].casefold() in r['content'].casefold())]
            if request['op'] == 'get' and not selected:
                return result('DENIED')
        if mutation == 'serialized-provenance':
            for row in selected:
                for key in ('provenance','semantic_status'):
                    updates = e['claims'].get(key,{})
                    if isinstance(updates,dict) and row['id'] in updates:
                        row[key] = updates[row['id']]
        return packed(selected, e, b['context_id'])
    except (ValueError, TypeError, KeyError, AttributeError, Rejected):
        # No raw IDs, file paths, input fragments or tracebacks in caller errors.
        return result('INVALID_CONTEXT')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--state', required=True)
    ap.add_argument('--envelope', required=True)
    ap.add_argument('--attestation', required=True)
    ap.add_argument('--checkpoint')
    ap.add_argument('--participant', choices=['cognition','worker','verifier'], default='worker')
    ap.add_argument('--mutation', choices=['serialized-scope','stale-policy','serialized-provenance'])
    args = ap.parse_args()
    Path(args.attestation).write_text(wire({'pid':os.getpid(),'ppid':os.getppid()}))
    try:
        state = parse(Path(args.state).read_text())
        raw = Path(args.envelope).read_text()
        out = receive(raw, state, participant=args.participant, mutation=args.mutation)
        if args.checkpoint:
            # Historical response is persisted for the negative-control opportunity,
            # never restored as current authority by receive(). Writer then exits.
            e = parse(raw)
            e['claims']['historical_packet'] = out
            Path(args.checkpoint).write_text(wire(e))
        print(wire(out))
    except (OSError, ValueError):
        print(wire(result('UNAVAILABLE')))


if __name__ == '__main__':
    main()

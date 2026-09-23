"""Independent source, prompt and raw-decision oracle evaluation; no selector imports."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def read(n):return json.loads((HERE/n).read_text())
def wire(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def sources(rev):
    rows={};files={}
    for p in sorted((HERE/'workspace'/rev).rglob('*.py')):
        rel=str(p.relative_to(HERE/'workspace'/rev));files[rel]=sha(p);text=p.read_text();module=ast.parse(text)
        imports={a.name for n in module.body if isinstance(n,ast.ImportFrom) for a in n.names}
        for n in module.body:
            if not isinstance(n,(ast.ClassDef,ast.FunctionDef)):continue
            rows[rel+'::'+n.name]={'line':n.lineno,'text':'\n'.join(text.splitlines()[n.lineno-1:n.end_lineno]),'hash':files[rel],'symbol':n.name,
                'inherits':{ast.unparse(b) for b in n.bases} if isinstance(n,ast.ClassDef) else set(),'calls':{ast.unparse(c.func) for c in ast.walk(n) if isinstance(c,ast.Call)},'imports':imports}
    scope='sha256:'+hashlib.sha256(wire({p:h for p,h in files.items() if p.startswith('personal/')})).hexdigest()
    return rows,files,scope


def answer(run):
    # Parse the raw provider output, not the runner's parsed/verified fields.
    for turn in run['turns']:
        if turn.get('error'):continue
        for record in turn['transport']:
            try:
                response=record['response'];choice=response['choices'][0]
                if len(response['choices'])!=1 or choice['finish_reason']!='stop':continue
                value=json.loads(choice['message']['content']);p=value['payload'];sent=turn['packet']['payload']
                if value.get('version')!=1 or value.get('kind')!='CognitiveDecision' or any(p[k]!=sent[k] for k in ('task_id','task_revision','turn_id')):continue
                action=p['next_action'];args=action.get('input',{})
                if action['type']!='INVOKE_CAPABILITY' or action.get('capability')!='artifact.write' or set(args)!={'name','content'} or args['name']!='answer':continue
                try:a=json.loads(args['content'])
                except (ValueError,TypeError):return None
                if a=={'decision':'CREATE_NEW'}:return a
                if isinstance(a,dict) and set(a)=={'decision','existing_target'} and a['decision']=='REUSE_EXISTING' and isinstance(a['existing_target'],str) and a['existing_target']:return a
                return None
            except (ValueError,TypeError,KeyError,IndexError):continue
    return None


def correct(a,o):return bool(a and a['decision']==o['decision'] and (a['decision']=='CREATE_NEW' or a['existing_target']==o['existing_target']))


def main(mutation_only=False):
    checks=[]
    def check(n,v):checks.append({'check':n,'pass':bool(v)})
    fixtures=read('proposals.json');oracle=read('oracles.json');policy=read('protocol.json');freeze=read('evidence/preregistration.json');initial=read('evidence/fixture-freeze.json')
    check('fixture-freeze',all(sha(HERE/p)==h for p,h in initial['files'].items()))
    check('behavior-freeze',all(sha(HERE/p)==h for p,h in freeze['files'].items()))
    check('unchanged-iii8r-policy',(HERE/'policy.json').read_bytes()==(HERE.parent/'track-iii-008r/policy.json').read_bytes())
    check('12-frozen-proposals',len(fixtures)==12 and all(sum(t['group']==g for t in fixtures)==4 for g in ('DUPLICATE','LEGITIMATE_ADDITION','NEAR_MATCH_MISMATCH')))
    check('thresholds',policy['threshold']=={'duplicate_reduction_each_repeat':2,'verified_reuse_improvement_each_repeat':2,'legitimate_correct_on_each_repeat':4,'near_match_correct_on_each_repeat':4,'regressions_max':0,'stale_max':0,'forbidden_max':0,'mutation_false_equivalence_min':1} and policy['packet_bytes']==2048 and policy['budget_actions']==3 and policy['repetitions']==2)
    advisory=read('evidence/advisory-results.json');packets={r['query']:r['output'] for r in advisory if r['revision']=='B'}
    stale=[];forbidden=[];candidate_metrics=[];maxbytes=0
    live,files,scope=sources('B');security=read('security.json')
    for rev in ('A','B'):
        _,f,_=sources(rev);check('revision/'+rev,read('revisions.json')[rev]=={'id':'sha256:'+hashlib.sha256(wire(f)).hexdigest(),'files':f})
    for row in [r for r in advisory if r['revision']=='B']:
        output=row['output'];ids={e['target'] for e in output['entries']};qid=row['query'];size=len(wire(output));maxbytes=max(maxbytes,size)
        check('packet-budget/'+qid,size<=2048 and size==row['complete_bytes']);check('visible-revision/'+qid,output['revision']==scope and row['derived_revision']==scope)
        for e in output['entries']:
            r=live.get(e['target'])
            if not r or r['line']!=e['line'] or r['text'][:80]!=e['excerpt']:stale.append({'task':qid,'target':e['target']})
            if not e['target'].startswith('personal/'):forbidden.append({'task':qid,'target':e['target']})
        for a,rel,b in output['relations']:
            s=live.get(output['entries'][a]['target']);t=live.get(output['entries'][b]['target'])
            if not s or not t or t['symbol'] not in s[rel]:stale.append({'task':qid,'edge':[a,rel,b]})
        if any(s in wire(output).decode() for s in security['forbidden_literals']):forbidden.append({'task':qid,'literal':True})
        expected=oracle[qid]['required_candidate'];raw={m:{x['target'] for x in hits} for m,hits in row['raw'].items()};hit=next((e for e in output['entries'] if e['target']==expected),None)
        candidate_metrics.append({'task':qid,'required_candidate':expected,'broad':any(expected in s for s in raw.values()),'included':expected in ids,'selected_mechanisms':hit['via'] if hit else None,'lexical_found':expected in raw['LEXICAL'],'bytes':size,'excerpt':hit['excerpt'] if hit else None})
    check('zero-stale',not stale);check('zero-forbidden',not forbidden)
    canonical=next(c for c in candidate_metrics if c['task']=='D1')
    check('canonical-broad-nonlexical',canonical['broad'] and canonical['included'] and not canonical['lexical_found'] and 'S' in canonical['selected_mechanisms'])
    safe=read('evidence/advisory-stale-safe.json');removed=[]
    for r in [r for r in safe if r['revision']=='B']:
        invalid={c['target'] for c in r['contributions'] if c['reasons']};removed.extend(invalid)
        check('stale-derived-excluded/'+r['query'],r['output']['derived_state']=='STALE_EXCLUDED' and all(e['via']=='L' and e['target'] in live and e['excerpt']==live[e['target']]['text'][:80] for e in r['output']['entries']))
        check('fallback-valid-contributions/'+r['query'],all(not c['reasons'] for c in r['contributions'] if c['mechanism']=='LEXICAL'))
    check('attractive-stale-candidate-exercised','personal/old/fold.py::ArchivedFold' in removed)
    hidden=read('evidence/protected-candidates.json');check('relevant-protected-candidate',any(x['target']=='employer-x/vault.py::VaultFold' for r in hidden if r['query']=='D1' for x in r['raw']['SEMANTIC'][:5]))
    runs=read('evidence/behavior.json');mutants=read('evidence/mutation.json')
    check('complete-primary-pairs',len(runs)==48 and {(r['repeat'],r['task'],r['condition']) for r in runs}=={(rep,t['id'],c) for rep in range(2) for t in fixtures for c in ('OFF','ON')})
    check('complete-mutation-pairs',len(mutants)==2 and {(m['task'],m['repeat']) for m in mutants}=={('N1',0),('N1',1)})
    decisions=[];invocations=0
    for run in runs+mutants:
        key=str(run['repeat'])+'/'+run['task']+'/'+run['condition'];t=next(t for t in fixtures if t['id']==run['task']);a=answer(run);ok=correct(a,oracle[t['id']]);decisions.append({'repeat':run['repeat'],'task':t['id'],'condition':run['condition'],'group':t['group'],'answer':a,'correct':ok})
        check('valid-run/'+key,not run['blocked'] and 1<=len(run['turns'])<=3 and a==run['parsed'])
        supplied=run['supplied']
        if run['condition']=='OFF':check('off-no-advice/'+key,supplied is None)
        elif run['condition']=='ON':check('on-exact-advice/'+key,supplied==packets[t['id']])
        else:
            expected=json.loads(json.dumps(packets[t['id']]))
            for e in expected['entries']:
                if e['target']=='personal/lib/fold.py::RuneFold':e['excerpt']='class RuneFold:\n    """Strip edges only; preserve all inner characters and case."""'
            check('isolated-mutation/'+key,supplied==expected)
            if mutation_only:check('contract-oracle/'+key,ok)
        if supplied is not None:check('model-advisory-budget/'+key,len(wire(supplied))<=2048)
        expected_facts={k:t[k] for k in ('proposal','proposed_name','contract','local_evidence')}
        for turn in run['turns']:
            payload=turn['packet']['payload'];check('identical-current-evidence/'+key+'/'+str(turn['index']),payload['objective']=='Choose reuse versus create for the current evidence: '+wire(expected_facts).decode() and payload['instructions']==freeze['guidance']+freeze['instructions'] and payload['allowed_capabilities']==['artifact.read','artifact.write'] and payload['limits']['remaining_actions']==3-turn['index'])
            if supplied is not None:check('model-received-advice/'+key+'/'+str(turn['index']),payload['observations'][0]==supplied)
            check('model-input-no-forbidden/'+key+'/'+str(turn['index']),not any(s in wire(turn['packet']).decode() for s in security['forbidden_literals']))
            for io in turn['transport']:
                invocations+=1;req=io['request'];check('local-model-config/'+key+'/'+str(turn['index']),req['model']==policy['model'] and req['temperature']==0 and req['max_tokens']==768 and req['chat_template_kwargs']=={'enable_thinking':False} and json.loads(req['messages'][1]['content'])==turn['packet'] and io['response'].get('model')==policy['model'])
    check('call-accounting',invocations==len(list((HERE/'evidence/calls').glob('*.json'))) and invocations<=150 and not list((HERE/'evidence/calls').glob('*.pending')))
    totals=[];regressions=[]
    for rep in range(2):
        groups={}
        for group in ('DUPLICATE','LEGITIMATE_ADDITION','NEAR_MATCH_MISMATCH'):
            entries=[d for d in decisions if d['repeat']==rep and d['group']==group and d['condition'] in ('OFF','ON')]
            by={c:[d for d in entries if d['condition']==c] for c in ('OFF','ON')}
            g={c:{'correct':sum(d['correct'] for d in by[c]),'create_new':sum(d['answer']=={'decision':'CREATE_NEW'} for d in by[c]),'reuse_existing':sum(bool(d['answer'] and d['answer']['decision']=='REUSE_EXISTING') for d in by[c])} for c in by}
            g['regressions']=[d['task'] for d in by['OFF'] if d['correct'] and not next(m for m in by['ON'] if m['task']==d['task'])['correct']];groups[group]=g
            if group!='DUPLICATE':
                check('absolute-correct/'+str(rep)+'/'+group,g['ON']['correct']==4);check('zero-regression/'+str(rep)+'/'+group,not g['regressions']);regressions.extend(g['regressions'])
        delta=groups['DUPLICATE']['OFF']['create_new']-groups['DUPLICATE']['ON']['create_new']
        verified_delta=groups['DUPLICATE']['ON']['correct']-groups['DUPLICATE']['OFF']['correct']
        check('duplicate-reduction/'+str(rep),delta>=2 and verified_delta>=2)
        totals.append({'repeat':rep,'groups':groups,'duplicate_reduction':delta,'verified_reuse_improvement':verified_delta})
    mutation_errors=[d for d in decisions if d['condition']=='FALSE_EQUIVALENCE' and d['answer'] and d['answer']['decision']=='REUSE_EXISTING' and next(o for o in decisions if o['repeat']==d['repeat'] and o['task']==d['task'] and o['condition']=='ON')['correct']]
    check('actual-behavioral-mutation',len(mutation_errors)>=1)
    variance=[{'task':t['id'],'condition':c} for t in fixtures for c in ('OFF','ON') if next(d for d in decisions if d['task']==t['id'] and d['condition']==c and d['repeat']==0)['answer']!=next(d for d in decisions if d['task']==t['id'] and d['condition']==c and d['repeat']==1)['answer']]
    report={'status':'PASS' if all(c['pass'] for c in checks) else 'FAIL','checks':checks,'failed':[c['check'] for c in checks if not c['pass']],'totals':totals,'decisions':decisions,'candidate_metrics':candidate_metrics,'stale':stale,'forbidden':forbidden,'max_packet_bytes':maxbytes,'cognition_invocations':invocations,'mutation_false_equivalences':len(mutation_errors),'decision_variance':variance,'structural_incremental_utility':'UNPROVEN: no structural-only behavioral ablation','III_8_status':'FAIL','III_8R_status':'PASS','III_10_started':False}
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--mutation-only',action='store_true');p.add_argument('--output',default='evidence/verification.json');a=p.parse_args();r=main(a.mutation_only)
    path=HERE/a.output;path.write_text(json.dumps(r,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:r[k] for k in ('status','failed','totals','cognition_invocations','mutation_false_equivalences','decision_variance','max_packet_bytes')}))
    raise SystemExit(int(r['status']!='PASS'))

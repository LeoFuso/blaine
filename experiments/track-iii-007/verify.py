"""Independent retained-evidence checker. JSON only; no evaluator/model imports."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def read(name):return json.loads((HERE/name).read_text())
def wire(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def sha(x):return hashlib.sha256(wire(x)).hexdigest()
def expected(task):
    rule=task['rule'];facts=task['facts']
    return str(sum(facts['values'])) if rule.get('operation')=='sum' else str(rule['multiplier']*facts['x']+rule['offset'])

def replay(run,task):
    artifact=None
    for turn in run['turns']:
        d=turn.get('decision')
        if not d:continue
        action=d['payload']['next_action'];args=action.get('input',{})
        if artifact is None and action.get('type')=='INVOKE_CAPABILITY' and action.get('capability')=='artifact.write' and set(args)=={'name','content'} and args['name']=='answer':artifact=args['content']
    return artifact,artifact==expected(task)


def main():
    p=argparse.ArgumentParser();p.add_argument('--mutation-only',action='store_true');args=p.parse_args()
    f=read('fixtures.json');tasks={t['id']:t for t in f['tasks']};mutations=read('evidence/mutation.json')
    if args.mutation_only:
        failures=[{'task':m['task'],'repeat':m['repeat'],'expected':expected(tasks[m['task']]),'actual':replay(m,tasks[m['task']])[0]} for m in mutations if not replay(m,tasks[m['task']])[1]]
        report={'status':'FAIL' if failures else 'PASS','failures':failures,'oracle':'Original unchanged exact-answer verifier against mutated model decisions.'}
        print(json.dumps(report,sort_keys=True));return int(bool(failures))
    checks=[]
    def check(name,condition):checks.append({'check':name,'status':'PASS' if condition else 'FAIL'})
    reg=read('evidence/preregistration.json');protocol=read('protocol.json');s=read('evidence/summary.json');c=read('evidence/composition.json');runs=read('evidence/behavior.json')
    check('predeclared',reg['protocol']==protocol and reg['model_calls_before_freeze']==0 and protocol['threshold']=={'matching_delta_min_each_repeat':2,'paired_irrelevant_regressions_max':0,'paired_trap_regressions_max':0,'structural_checks_required':True,'behavioral_mutation_regression_min':1})
    check('frozen-inputs',all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==h for n,h in reg['source_sha256'].items()))
    check('all-fixture-answers',all(t['expected']==expected(t) for t in tasks.values()))
    check('three-groups',len(tasks)==12 and all(sum(t['group']==g for t in tasks.values())==4 for g in ('MATCHING','IRRELEVANT','NEAR_MATCH_TRAP')))
    expected_keys={(rep,t,cond) for rep in range(2) for t in tasks for cond in ('NO_MEMORY','MEMORY')}
    by_key={(r['repeat'],r['task'],r['condition']):r for r in runs}
    check('all-pairs',len(by_key)==len(runs)==48 and set(by_key)==expected_keys)
    check('composition-oracles',c['status']=='PASS' and all(x['actual']==x['expected'] and x['status']=='PASS' for x in c['checks']))
    check('composition-restored',c==read('evidence/restored.json'))
    origins={o['key']:o for o in c['origins']};destinations={o['destination']['id']:o['destination'] for o in c['origins']}
    for key,o in origins.items():
        source=o['source'];dest=o['destination'];prov=o['private_provenance']['derived_from'];spec=f['executions'][o['execution']]
        check('origin/'+key,source['provenance']==dest['provenance'] and source['epistemic_status']==dest['epistemic_status'] and source['content']==dest['content'] and source['context_id']!=dest['context_id'] and source['id']!=dest['id'] and dest['domain']==source['domain'] and dest['classification']=='PRIVATE')
        check('authoritative-link/'+key,prov['execution_id']==o['execution'] and prov['envelope']==f['envelopes'][o['execution']] and prov['requirements']==spec['requirements'] and prov['evidence']==[f['evidence'][q['id']] for q in spec['requirements']])
        if key!='uncertain':
            positive=source['epistemic_status']=='VERIFIED_SUCCESS'
            check('verified-provenance/'+key,source['provenance']=='VERIFIED_OUTCOME' and prov['envelope']['status']==('SUCCEEDED' if positive else 'FAILED') and prov['evidence'][0]['result']==('PASS' if positive else 'FAIL'))
        else:check('unverified-not-upgraded',dest['provenance']=='AGENT_OBSERVATION' and dest['epistemic_status']=='UNVERIFIED')
    for v in c['visibility']:
        allowed=v['kind']=='destination' and v['key']!='protected'
        check('isolation/'+v['task']+'/'+v['key']+'/'+v['kind'],v['response']['status']==('SUCCESS_WITH_RESULTS' if allowed else 'DENIED') and (bool(v['response']['entries']) if allowed else v['response']['entries']==[]))
    for cross in c['cross_boundary']:
        expected_state={'raw':'REJECTED_SECURITY','safe':'ADMITTED','unavailable':'UNAVAILABLE','unknown':'REJECTED_SCANNER','forged':'REJECTED_POLICY','authority':'REJECTED_AUTHORITY'}[cross['mode']]
        check('cross/'+cross['mode'],cross['response']['status']==expected_state)
    check('cross-replay-current-scanner',next(x for x in c['cross_boundary'] if x['mode']=='safe')['replay']['status']=='UNAVAILABLE')
    check('human-path',c['human_declaration']['response']['receipt']['provenance']=='USER_DECLARATION')
    leaks=[];max_bytes=0;actual={};input_sizes=[];invocations=0
    for r in runs+mutations:
        key=str((r['repeat'],r['task'],r['condition']));t=tasks[r['task']];value,passed=replay(r,t);actual[(r['repeat'],r['task'],r['condition'])]=passed
        check('actual-verifier/'+key,not r['blocked'] and r['artifact']==value and r['verified']==passed and r['expected']==expected(t))
        check('visible-metadata/'+key,set(r['visible_ids'])=={i for i,e in destinations.items() if e['domain']=='personal'})
        check('budget/'+key,1<=len(r['turns'])<=3 and [t['index'] for t in r['turns']]==list(range(len(r['turns']))))
        for turn in r['turns']:
            invocations+=1;retrieved=turn['retrieved'];supplied=turn['supplied'];packet=turn['packet'];body=turn['transport'][0]['request'];reply=turn['transport'][0]['response']
            max_bytes=max(max_bytes,len(wire(retrieved)),len(wire(supplied)) if supplied else 0)
            check('retrieval/'+key+'/'+str(turn['index']),retrieved['status']=='SUCCESS_WITH_RESULTS' and not retrieved['partial'] and all(e['id'] in destinations and e['id']!=origins['protected']['destination']['id'] and {k:v for k,v in e.items() if k!='kind'}==destinations[e['id']] for e in retrieved['entries']))
            check('instruction-identity/'+key+'/'+str(turn['index']),packet['payload']['instructions']==reg['instructions'] and packet['payload']['limits']['max_turns']==3 and packet['payload']['limits']['remaining_actions']==3-turn['index'])
            check('model-input/'+key+'/'+str(turn['index']),json.loads(body['messages'][1]['content'])==packet and body['model']==protocol['model'] and reply['model']==protocol['model'] and body['temperature']==0 and body['max_tokens']==768 and body['chat_template_kwargs']=={'enable_thinking':False})
            if turn['decision']:
                check('raw-decision/'+key+'/'+str(turn['index']),json.loads(reply['choices'][0]['message']['content'])==turn['decision'])
            else:
                try:json.loads(reply['choices'][0]['message']['content']);invalid=False
                except (ValueError,TypeError):invalid=True
                check('invalid-consumes-budget/'+key+'/'+str(turn['index']),invalid and turn['operation_result']=={'status':'INVALID_DECISION'} and turn['audit'][0]['outcome']=='rejected')
            if r['condition']=='NO_MEMORY':check('withheld/'+key+'/'+str(turn['index']),supplied is None and packet['payload']['context']==[])
            else:
                check('packet-memory/'+key+'/'+str(turn['index']),packet['payload']['context'][0]['content']==supplied)
                if r['condition']=='MEMORY':check('correct-render/'+key+'/'+str(turn['index']),supplied==retrieved)
                else:
                    changed=[(before,after) for before,after in zip(retrieved['entries'],supplied['entries']) if before!=after]
                    check('isolated-mutation/'+key+'/'+str(turn['index']),len(changed)==1 and changed[0][0]['epistemic_status']=='VERIFIED_FAILURE' and changed[0][1]['epistemic_status']=='VERIFIED_SUCCESS' and changed[0][0]['id']==changed[0][1]['id'])
            for label,obj in [('retrieval',retrieved),('prompt',body),('reply',reply)]:
                hits=[lit for lit in f['protected_literals']+f['private_literals'] if lit in wire(obj).decode()]
                if hits:leaks.append({'run':key,'turn':turn['index'],'surface':label,'literals':hits})
    check('bounded-packets',max_bytes<=2048)
    check('literal-leaks',leaks==[])
    check('invocation-count',invocations==s['model_invocations'] and invocations<=protocol['maximum_model_invocations'])
    check('multi-memory-control',len(by_key[(0,'match-1','MEMORY')]['turns'][0]['retrieved']['entries'])>=3)
    # Initial packets differ only in the memory context. Later observations may differ by actions.
    for rep in range(2):
        for task in tasks:
            b=json.loads(json.dumps(by_key[(rep,task,'NO_MEMORY')]['turns'][0]['packet']));m=json.loads(json.dumps(by_key[(rep,task,'MEMORY')]['turns'][0]['packet']))
            m['payload']['context']=[];check('paired-input/'+str(rep)+'/'+task,b==m)
    totals=[];regressions=[]
    for rep in range(2):
        groups={}
        for group in ('MATCHING','IRRELEVANT','NEAR_MATCH_TRAP'):
            group_tasks=[t for t in tasks if tasks[t]['group']==group]
            counts={cond:sum(actual[(rep,t,cond)] for t in group_tasks) for cond in ('NO_MEMORY','MEMORY')}
            groups[group]={**counts,'delta':counts['MEMORY']-counts['NO_MEMORY']}
        losses=[t for t in tasks if tasks[t]['group']!='MATCHING' and actual[(rep,t,'NO_MEMORY')] and not actual[(rep,t,'MEMORY')]]
        regressions.extend(losses);totals.append({'repeat':rep,'groups':groups,'regressions':losses})
        check('utility-threshold/'+str(rep),groups['MATCHING']['delta']>=2 and not losses)
    check('independent-totals',totals==s['totals'])
    mutation_losses=sum(actual[(m['repeat'],m['task'],'MEMORY')] and not actual[(m['repeat'],m['task'],'FAILURE_AS_SUCCESS')] for m in mutations)
    control=read('evidence/mutation-control.json')
    check('behavioral-mutation',mutation_losses>=1 and mutation_losses==s['mutation_regressions'] and control['exit_code']==1 and control['result']['status']=='FAIL')
    variance=[]
    for task in tasks:
        for cond in ('NO_MEMORY','MEMORY'):
            a=by_key[(0,task,cond)];b=by_key[(1,task,cond)]
            variance.append({'task':task,'condition':cond,'completion_changed':actual[(0,task,cond)]!=actual[(1,task,cond)],'decisions_changed':[t['decision'] for t in a['turns']]!=[t['decision'] for t in b['turns']]})
    check('summary-consistent',s['status']=='PASS' and not s['III_8_started'] and s['source_freeze_unchanged'] and s['composition_unchanged_after_mutation'])
    metrics={'calls_by_group':{g:{cond:sum(len(r['turns']) for r in runs if r['group']==g and r['condition']==cond) for cond in ('NO_MEMORY','MEMORY')} for g in ('MATCHING','IRRELEVANT','NEAR_MATCH_TRAP')},
             'invalid_decisions':[{'task':r['task'],'condition':r['condition'],'repeat':r['repeat'],'turn':t['index']} for r in runs+mutations for t in r['turns'] if t['error']],
             'reported_usage':{field:sum(t['transport'][0]['response'].get('usage',{}).get(field,0) for r in runs+mutations for t in r['turns']) for field in ('prompt_tokens','completion_tokens','total_tokens')}}
    evidence_status='PASS' if all(x['status']=='PASS' for x in checks) else 'FAIL'
    report={'status':evidence_status,'checks':checks,'check_count':len(checks),'totals':totals,'mutation_regressions':mutation_losses,'leaks':leaks,'max_packet_bytes':max_bytes,'model_invocations':invocations,'variance':variance,'metrics':metrics}
    (HERE/'evidence/verification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:report[k] for k in ('status','check_count','totals','mutation_regressions','max_packet_bytes','model_invocations')}))
    return int(evidence_status!='PASS')


if __name__=='__main__':raise SystemExit(main())

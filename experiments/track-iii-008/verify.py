"""Independent source/oracle/evidence checks. Does not import discovery/index code."""
import argparse
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def read(n):return json.loads((HERE/n).read_text())
def wire(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(wire(x)).hexdigest()
def sources(rev):
    rows={};files={}
    for p in sorted((HERE/'workspace'/rev).rglob('*.py')):
        rel=str(p.relative_to(HERE/'workspace'/rev));text=p.read_text();lines=text.splitlines();sha=hashlib.sha256(p.read_bytes()).hexdigest();files[rel]=sha;tree=ast.parse(text)
        imports=[a.name for n in tree.body if isinstance(n,ast.ImportFrom) for a in n.names]
        for n in tree.body:
            name=n.name if isinstance(n,(ast.FunctionDef,ast.ClassDef)) else n.targets[0].id if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) else None
            if name:rows[rel+'::'+name]={'hash':sha,'line':n.lineno,'text':'\n'.join(lines[n.lineno-1:n.end_lineno]),'name':name,'calls':{ast.unparse(c.func) for c in ast.walk(n) if isinstance(c,ast.Call)},'imports':set(imports),'bases':{ast.unparse(b) for b in n.bases} if isinstance(n,ast.ClassDef) else set()}
    return rows,files

def main():
    p=argparse.ArgumentParser();p.add_argument('input',nargs='?',default='evidence/results.json');p.add_argument('--control',action='store_true');p.add_argument('--output',default='evidence/verification.json');args=p.parse_args()
    results=read(args.input);queries=read('queries.json');oracle=read('oracles.json');sec=read('security.json');protocol=read('protocol.json');revs=read('revisions.json');reg=read('evidence/preregistration.json')
    checks=[];details=[];stale=[];forbidden=[];max_bytes=0;max_envelope=0
    def check(n,c):checks.append({'check':n,'status':'PASS' if c else 'FAIL'})
    check('query-taxonomy',len(queries)==12 and all(sum(q['group']==g for q in queries)==4 for g in ('LEXICAL','SEMANTIC','STRUCTURAL')))
    check('threshold-frozen',protocol['required_nonlexical_gain']==2 and protocol['packet_bytes']==2048 and protocol['exact_losses_max']==protocol['stale_emitted_max']==protocol['forbidden_emitted_max']==0)
    correction=read('evidence/budget-correction.json')
    before=(HERE/'evidence/initial-payload-only/discover.py.txt').read_text();after=(HERE/'discover.py').read_text()
    old="if len(wire(proposed))+1<=2048:packet=proposed"
    new="envelope={'packet':proposed,'diagnostic':{'status':proposed['status'],'selected':len(proposed['entries']),'partial':True}}\n            if len(wire(envelope))+2<=2048:packet=proposed"
    check('budget-only-correction',before.replace(old,new)==after and hashlib.sha256(before.encode()).hexdigest()==reg['source_sha256']['discover.py']==correction['before_sha256'] and hashlib.sha256(after.encode()).hexdigest()==correction['after_sha256'])
    check('frozen-files',reg['prior_comparative_runs']==0 and all(hashlib.sha256((HERE/p).read_bytes()).hexdigest()==h for p,h in reg['source_sha256'].items() if p!='discover.py'))
    expected={(rev,q['id'],mode) for rev in ('A','B') for q in queries for mode in ('LEXICAL','COMBINED')};actual={(r['revision'],r['query'],r['mode']) for r in results}
    check('all-48-comparisons',len(results)==48 and actual==expected)
    for rev in ('A','B'):
        rows,files=sources(rev);rid='sha256:'+digest(files);scope='sha256:'+digest({p:h for p,h in files.items() if p.startswith('personal/')})
        check('source-revision/'+rev,revs[rev]=={'id':rid,'files':files})
        for r in [r for r in results if r['revision']==rev]:
            key=rev+'/'+r['query']+'/'+r['mode'];packet=r['output']['packet'];ids={e['target'] for e in packet['entries']};wanted=set(oracle[rev][r['query']]['required']);accepted=set(oracle[rev][r['query']]['acceptable']);size=len(wire(packet));max_bytes=max(max_bytes,size)
            envelope_size=len(wire(r['output']));max_envelope=max(max_envelope,envelope_size)
            check('envelope-budget/'+key,envelope_size<=2048)
            check('packet-revision/'+key,packet['revision']==scope)
            check('packet-budget/'+key,size<=2048 and r['metrics']['packet_bytes']==size)
            check('raw-metrics/'+key,r['metrics']['raw_count']==len(r['candidates']) and r['metrics']['raw_bytes']==len(wire(r['candidates'])) and r['metrics']['selected_count']==len(packet['entries']))
            check('no-duplicate-targets/'+key,len(ids)==len(packet['entries']))
            for e in packet['entries']:
                source=rows.get(e['target']);bad=not source or source['hash']!=e['source_hash'] or source['line']!=e['line'] or not source['text'].startswith(e['excerpt'])
                if any(v!='LEXICAL' for v in e['via']) and packet['derived_revision']!=scope:bad=True
                if bad:stale.append({'case':key,'target':e['target']})
                if not e['target'].startswith('personal/'):forbidden.append({'case':key,'target':e['target']})
                check('mechanism-origin/'+key+'/'+e['target'],all(e['target'] in {v['target'] for v in r['raw'][m]} for m in e['via']))
            for e in packet['relations']:
                a=rows.get(e['source']);b=rows.get(e['target'])
                valid=a and b and b['name'] in a[{'calls':'calls','inherits':'bases','imports':'imports'}[e['relation']]]
                if not valid:stale.append({'case':key,'relation':e})
                if not all(t.startswith('personal/') for t in (e['source'],e['target'])):forbidden.append({'case':key,'relation':e})
            hits=[s for s in sec['forbidden_literals'] if s in wire(r['output']).decode()]
            if hits:forbidden.append({'case':key,'literals':hits})
            if not args.control:
                check('prefilter-all-mechanisms/'+key,all(x['target'].startswith('personal/') for raw in r['raw'].values() for x in raw))
            detail={'revision':rev,'query':r['query'],'group':r['group'],'mode':r['mode'],'required_hits':sorted(ids&wanted),'acceptable_hits':sorted(ids&accepted),'misses':sorted(wanted-ids),'raw_required_hits':sorted(set(r['candidates'])&wanted),'packet_bytes':size,'caller_visible_bytes':envelope_size,'raw_count':r['metrics']['raw_count'],'raw_bytes':r['metrics']['raw_bytes'],'selected_count':len(ids),'omitted':r['omitted'],'stale_candidates':r['metrics']['stale_candidates'],'forbidden_candidates':len(r['metrics']['forbidden_partition_targets']),'stale_emitted_references':sum(x['case']==key for x in stale),'forbidden_emitted_references':sum(x['case']==key and ('target' in x or 'relation' in x) for x in forbidden),'selected_mechanisms':{e['target']:e['via'] for e in packet['entries']}}
            details.append(detail)
            if r['mode']=='COMBINED' and not args.control:check('final-required-coverage/'+key,not wanted-ids)
    aggregate=[]
    for rev in ('A','B'):
        gains={'SEMANTIC':set(),'STRUCTURAL':set()};losses=[];exact_before=exact_after=0
        for q in queries:
            b=next(d for d in details if d['revision']==rev and d['query']==q['id'] and d['mode']=='LEXICAL');c=next(d for d in details if d['revision']==rev and d['query']==q['id'] and d['mode']=='COMBINED')
            before=set(b['required_hits']);after=set(c['required_hits'])
            if q['group']=='LEXICAL':
                exact_before+=len(before);exact_after+=len(after);losses.extend(sorted(before-after))
            else:gains[q['group']].update(after-before)
        all_gains=gains['SEMANTIC']|gains['STRUCTURAL'];entry={'revision':rev,'exact_baseline':exact_before,'exact_combined':exact_after,'exact_losses':losses,'semantic_gains':sorted(gains['SEMANTIC']),'structural_gains':sorted(gains['STRUCTURAL']),'unique_nonlexical_gains':sorted(all_gains),'gain_count':len(all_gains)};aggregate.append(entry)
        if not args.control:
            check('exact-retention/'+rev,not losses and exact_before==exact_after==4)
            check('gain-threshold/'+rev,len(all_gains)>=2)
            novelty=next(d for d in details if d['revision']==rev and d['query']=='S1' and d['mode']=='COMBINED');check('novelty/'+rev,bool(novelty['required_hits']))
    check('no-stale-emission',not stale);check('no-forbidden-emission',not forbidden)
    if not args.control:
        boundaries=read('evidence/boundaries.json')
        for c in boundaries['checks']:check('boundary/'+c['case'],c['expected']==c['actual'])
        controls=read('evidence/controls.json')
        check('freshness-control-caught',controls['freshness']['exit_code']==1 and controls['freshness']['result']['stale']>0 and controls['freshness']['result']['failed']==['no-stale-emission'])
        check('isolation-control-caught',controls['isolation']['exit_code']==1 and controls['isolation']['result']['forbidden']>0 and controls['isolation']['result']['failed']==['no-forbidden-emission'])
        safe=read('evidence/stale-safe.json')
        for row in safe:
            if row['revision']=='B' and row['mode']=='COMBINED':
                check('stale-index-excluded/'+row['query'],row['output']['packet']['derived_state']=='STALE_EXCLUDED' and all(e['via']==['LEXICAL'] for e in row['output']['packet']['entries']))
    report={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','check_count':len(checks),'checks':checks,'metrics':details,'aggregate':aggregate,'stale_emitted':stale,'forbidden_emitted':forbidden,'max_packet_bytes':max_bytes,'max_caller_visible_bytes':max_envelope}
    (HERE/args.output).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(checks),'aggregate':aggregate,'stale':len(stale),'forbidden':len(forbidden),'max_packet_bytes':max_bytes,'max_caller_visible_bytes':max_envelope,'failed':[c['check'] for c in checks if c['status']=='FAIL']}))
    return int(report['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())

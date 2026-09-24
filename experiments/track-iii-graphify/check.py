"""Independent packet/source oracle; no imports from discovery or evaluator."""
from collections import Counter,defaultdict
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from source import HERE,ROOTS,load,wire


def gz(p):return json.loads(gzip.decompress(Path(p).read_bytes()))
def triple(e):return(e['source'],e['relation'],e['target'])


def audit_packet(row,q,current='B'):
    repo=q['repo'];d=HERE/'evidence/indexes'/repo
    facts={rev:gz(d/rev/'source.json.gz') for rev in ['A','B']}
    manifest=load(HERE/'repositories.json')[repo]
    security=load(HERE/'security.json')[repo]
    p=row['packet']; nodes=[];stale=[];forbidden=[];unsupported=[];invalid=[];valid=[]
    for index,(file,symbol,line,revision) in enumerate(p['nodes']):
        file=ROOTS[repo]+'/'+file
        match=[k for k,n in facts.get(revision,{'nodes':{}})['nodes'].items() if n['file']==file and n['symbol']==symbol and n['line']==line]
        key=match[0] if len(match)==1 else None;nodes.append(key)
        if revision!=current or key not in facts[current]['nodes'] or facts[current]['nodes'].get(key,{}).get('line')!=line:
            stale.append(index)
        if file in security['denied_files']:forbidden.append(index)
    for literal in security['protected_literals']:
        if literal in wire(p):forbidden.append(literal)
    truth={triple(e) for e in facts[current]['edges']}
    returned=[]
    for i,a in enumerate(p['answers']):
        target=nodes[a['target']];returned.append(target);cursor=q['start'];bad=False
        if not a['steps'] or len(a['steps'])>q['depth']:bad=True
        for source,rel,dest,confidence,mechanisms in a['steps']:
            x=nodes[source];y=nodes[dest]
            if (x,rel,y) not in truth:unsupported.append([x,rel,y]);bad=True
            if rel not in q['relations']:bad=True
            if q['local'] and x and y and x.split('#')[0]!=y.split('#')[0]:bad=True
            u,v=(x,y) if q['direction']=='out' else (y,x)
            if cursor!=u:bad=True
            cursor=v
            if source in stale or dest in stale or source in forbidden or dest in forbidden:bad=True
            if not set(confidence)<={'EXTRACTED','INFERRED','SOURCE'}:bad=True
            if not set(mechanisms)<={'L','G'}:bad=True
        if cursor!=target or q['end'] and target!=q['end']:bad=True
        if q['scope'] and (not target or not target.startswith(q['scope'])):bad=True
        if bad:invalid.append(i)
        else:valid.append(target)
    errors=[]
    if p['revision']!=manifest[current]['commit'] or p['repo']!=repo:errors.append('revision binding')
    size=len(wire(p).encode())
    if size>2048 or size!=row['packet_bytes']:errors.append('complete packet bytes')
    if stale:errors.append('stale references')
    if forbidden:errors.append('forbidden references/metadata')
    if unsupported:errors.append('unsupported relations')
    if invalid:errors.append('invalid typed path')
    return dict(valid_targets=sorted(set(valid)),returned_targets=returned,stale=stale,forbidden=forbidden,
                unsupported=unsupported,invalid=invalid,errors=errors,packet_bytes=size)


def evaluate(control=None):
    checks=[]
    def check(label,value):checks.append({'check':label,'ok':bool(value)})
    freeze=load(HERE/'evidence/corpus-freeze.json')
    for file,h in freeze['sha256'].items():check('frozen '+file,hashlib.sha256((HERE/file).read_bytes()).hexdigest()==h)
    reg=load(HERE/'evidence/preregistration.json')
    corrections=load(HERE/'evidence/execution-errata.json')['corrections']
    for file,h in reg['sha256'].items():
        if file in corrections:
            correction=corrections[file]
            check('original implementation pin '+file,hashlib.sha256((HERE/correction['original']).read_bytes()).hexdigest()==h)
            check('documented execution correction '+file,hashlib.sha256((HERE/file).read_bytes()).hexdigest()==correction['corrected_sha256'])
        else:check('implementation/index pin '+file,hashlib.sha256((HERE/file).read_bytes()).hexdigest()==h)
    queries=load(HERE/'queries.json');by_id={q['id']:q for q in queries};oracles=load(HERE/'oracles.json')
    check('20 unique questions',len(queries)==len(by_id)==20)
    check('five per category',Counter(q['group'] for q in queries)==dict(DIRECT=5,MULTI_HOP=5,IMPACT=5,TRAP=5))
    check('ten per repository',Counter(q['repo'] for q in queries)=={'spring-kafka':10,'jackson-databind':10})
    if control:
        if control=='stale': rows=[(x['results']['stale'],x['query']) for x in load(HERE/'evidence/freshness.json')]
        elif control=='inferred':
            x=load(HERE/'evidence/inferred-mutation.json');rows=[(x['unsafe'],x['query'])]
        else:
            row=load(HERE/'evidence/isolation-mutation.json');rows=[(row,by_id[row['query']])]
        audits=[audit_packet(row,q) for row,q in rows]
        actual=any(a['stale'] for a in audits) if control=='stale' else any(a['forbidden'] for a in audits) if control=='isolation' else any(a['unsupported'] for a in audits)
        check('normal structural/security requirements hold under control',not any(a['errors'] for a in audits))
        return dict(status='PASS' if all(x['ok'] for x in checks) else 'FAIL',control=control,actual_violation=actual,audits=audits,checks=checks)
    # Verify oracle witnesses against retained unmodified authoritative source and facts.
    repos=load(HERE/'repositories.json')
    for repo,versions in repos.items():
        for rev in ['A','B']:
            d=HERE/'evidence/indexes'/repo/rev;f=gz(d/'source.json.gz')
            with tarfile.open(d/'source.tar.gz') as archive:
                for member in archive.getmembers():
                    b=archive.extractfile(member).read();check('source bytes '+repo+'/'+rev+'/'+member.name,
                        hashlib.sha256(b).hexdigest()==versions[rev]['manifest'][member.name])
            raw=gz(d/'raw.json.gz');cost=load(d/'cost.json')
            check('actual confidence counts '+repo+rev,dict(Counter(e.get('confidence','ABSENT') for e in raw['edges']))==cost['confidence'])
            check('no failed source '+repo+rev,not cost['failed_sources'])
        f=gz(HERE/'evidence/indexes'/repo/'B/source.json.gz');truth={triple(e) for e in f['edges']}
        for q in [q for q in queries if q['repo']==repo]:
            for target,witness in oracles[q['id']]['source_witnesses'].items():
                check('oracle supported '+q['id']+'/'+target,bool(witness) and all(triple(e) in truth for e in witness))
    rows=load(HERE/'evidence/results.json')
    check('sixty condition results',len(rows)==60 and len({(r['query'],r['condition']) for r in rows})==60)
    metrics=[];result={};gains={};totals=defaultdict(lambda:dict(required_hits=0,required_total=0,false_positives=0,unsupported=0,correct_negative=0,requests=0,source_files=0,validation_files=0,query_seconds=0))
    for row in rows:
        q=by_id[row['query']];oracle=oracles[q['id']];a=audit_packet(row,q)
        check('valid packet '+q['id']+row['condition'],not a['errors'])
        hits=sorted(set(a['valid_targets'])&set(oracle['required']))
        false=sorted(set(a['returned_targets'])-set(oracle['acceptable']),key=str)
        if row['condition']=='A':check('three source operations '+q['id'],len(row['discovery'])==1 and len(row['discovery'][0]['operations'])==3)
        if row['condition']=='B':check('one graph request '+q['id'],row['exploration_requests']==1)
        confidence=Counter(c for answer in row['packet']['answers'] for step in answer['steps'] for c in step[3])
        m=dict(query=q['id'],repo=q['repo'],group=q['group'],condition=row['condition'],required_hits=hits,
            required_total=len(oracle['required']),misses=sorted(set(oracle['required'])-set(hits)),false_positives=false,
            unsupported=a['unsupported'],stale=a['stale'],forbidden=a['forbidden'],packet_bytes=a['packet_bytes'],
            correct_negative=oracle['negative'] and not a['returned_targets'] and not a['errors'],
            requests=row['exploration_requests'],source_files=len(row['exploration_files']),validation_files=len(row['source_revalidation_files']),
            selected_confidence=dict(confidence),query_seconds=sum(d['seconds'] for d in row['discovery'])+row['assembly_seconds'])
        metrics.append(m);result[(q['id'],row['condition'])]=m
        for level in [(q['repo'],q['group'],row['condition']),('ALL',q['group'],row['condition'])]:
            t=totals[level];t['required_hits']+=len(hits);t['required_total']+=len(oracle['required']);t['false_positives']+=len(false)
            t['unsupported']+=len(a['unsupported']);t['correct_negative']+=int(m['correct_negative']);t['requests']+=m['requests']
            t['source_files']+=m['source_files'];t['validation_files']+=m['validation_files'];t['query_seconds']+=m['query_seconds']
    exact_losses=[];trap_regressions=[];reductions=[]
    for q in queries:
        a=result[q['id'],'A'];b=result[q['id'],'B'];c=result[q['id'],'C']
        if q['group']=='DIRECT' and not set(a['required_hits'])<=set(c['required_hits']):exact_losses.append(q['id'])
        if q['group']=='TRAP' and max(len(b['false_positives']),len(c['false_positives']))>len(a['false_positives']):trap_regressions.append(q['id'])
        if q['group'] in ('MULTI_HOP','IMPACT') and b['required_hits'] and set(a['required_hits'])<=set(b['required_hits']) and b['requests']<a['requests']:
            reductions.append(q['id'])
    for scope in ['ALL']+sorted(repos):
        scoped=[m for m in metrics if scope=='ALL' or m['repo']==scope]
        sets={c:{(m['repo'],target) for m in scoped if m['condition']==c for target in m['required_hits']} for c in ['A','B','C']}
        gains[scope]={c:sorted(sets[c]-sets['A']) for c in ['B','C']}
    check('three additional unique targets',max(len(gains['ALL']['B']),len(gains['ALL']['C']))>=3)
    check('zero lost direct targets',not exact_losses)
    check('zero trap regressions',not trap_regressions)
    check('three exploration reductions',len(reductions)>=3)
    freshness=[]
    for x in load(HERE/'evidence/freshness.json'):
        q=x['query'];aa=audit_packet(x['results']['A'],q,'A');bb=audit_packet(x['results']['B'],q)
        check('refreshed current safe '+q['repo'],not aa['errors'] and not bb['errors'])
        check('stale safe rejects derived '+q['repo'],not x['results']['stale_safe']['packet']['answers'])
        facts=gz(HERE/'evidence/indexes'/q['repo']/'B/source.json.gz')
        required={e['target'] for e in facts['edges'] if e['source']==q['start'] and e['relation']=='imports'}
        freshness.append(dict(repo=q['repo'],stale_emitted=len(bb['stale']),missing_current_refs=sorted(required-set(bb['valid_targets'])),
            removed_graph_edges=len(x['removed_graph_edges']),new_graph_edges=len(x['new_graph_edges']),
            removed_source_edges=len(x['removed_source_edges']),new_source_edges=len(x['new_source_edges'])))
    mutation=load(HERE/'evidence/inferred-mutation.json')
    check('inferred correct control abstains',not mutation['correct']['packet']['answers'])
    check('actual upstream inferred edge',mutation['actual_raw_edge']['confidence']=='INFERRED')
    for mode in ['stale','inferred']:
        r=evaluate(mode)
        check('actual caught '+mode+' mutation',r['status']=='FAIL' and r['actual_violation'])
    return dict(status='PASS' if all(c['ok'] for c in checks) else 'FAIL',checks=checks,
        failures=[c['check'] for c in checks if not c['ok']],metrics=metrics,
        totals=[dict(repo=k[0],group=k[1],condition=k[2],**v) for k,v in sorted(totals.items())],
        unique_gains=gains,exploration_reductions=reductions,direct_losses=exact_losses,trap_regressions=trap_regressions,
        max_packet_bytes=max(m['packet_bytes'] for m in metrics),stale_emitted=sum(len(m['stale']) for m in metrics),
        forbidden_emitted=sum(len(m['forbidden']) for m in metrics),freshness=freshness)


def main():
    p=argparse.ArgumentParser();p.add_argument('--control',choices=['stale','inferred','isolation']);p.add_argument('--output',type=Path);a=p.parse_args()
    try:r=evaluate(a.control)
    except (KeyError,ValueError,OSError,TypeError) as e:r={'status':'FAIL','failures':['incomplete or malformed evidence: '+str(e)]}
    text=json.dumps(r,sort_keys=True,indent=2)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')
    return 0 if r['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())

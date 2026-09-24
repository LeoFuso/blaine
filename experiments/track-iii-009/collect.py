"""Checkpointed use of existing BGE client and pinned Graphify extractor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from bind import HERE,collector,source,load,save,discover,selector,wire


def collect():
    assert subprocess.check_output(['git','-C',str(collector.UPSTREAM),'rev-parse','HEAD'],text=True).strip()==collector.PIN
    assert not subprocess.check_output(['git','-C',str(collector.UPSTREAM),'status','--porcelain'],text=True).strip()
    sys.path.insert(0,str(HERE.parents[1]/'infra/inference'))
    from accept import request
    save(HERE/'evidence/embedding-model.json',request(8001,'/v1/models',timeout=10))
    cache=HERE/'evidence/collection';cache.mkdir(exist_ok=True)
    vectors={};graphs={};indexes={};requests=[]
    def embed(key,ids,texts,domain):
        body={'model':'BAAI/bge-m3','input':texts};digest=hashlib.sha256(wire(body)).hexdigest();path=cache/(key+'.json')
        if path.exists():record=json.loads(path.read_text());assert record['request_sha256']==digest
        else:
            pending=cache/(key+'.pending')
            assert not pending.exists(),'Interrupted request has unknown completion; do not silently repeat it.'
            pending.write_text(digest)
            response=request(8001,'/v1/embeddings',body,timeout=60)
            record={'request':body,'request_sha256':digest,'response':response,'domain':domain,'ids':ids};save(path,record);pending.unlink()
        assert len(record['response']['data'])==len(ids)
        for r in record['response']['data']:
            assert len(r['embedding'])==1024
            vectors[ids[r['index']]]=r['embedding']
        requests.append({'key':key,'domain':domain,'request_sha256':digest,'input_ids':ids})
    for rev in ('A','B'):
        rows=source.declarations(rev);graphs[rev]={}
        for domain in ('personal','employer-x'):
            batch=[r for r in rows.values() if r['file'].startswith(domain+'/')]
            embed(rev+'-'+domain,[rev+'|'+r['target'] for r in batch],[r['text'] for r in batch],domain)
            path=cache/(rev+'-'+domain+'-graph.json')
            if not path.exists():
                with tempfile.TemporaryDirectory(prefix='iii9-graph-') as temp:
                    target=Path(temp)/'graph.json';env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(HERE.parents[1]/'experiments/graphify-carveout/offline'),'GRAPHIFY_QUERY_LOG_DISABLE':'1','GRAPHIFY_OUT':str(Path(temp)/'out')}
                    result=subprocess.run([collector.PYTHON,str(HERE/'collect.py'),'--graph-child',rev,domain,str(target)],env=env,capture_output=True,text=True,timeout=60)
                    assert result.returncode==0,result.stderr
                    save(path,json.loads(target.read_text()))
            graphs[rev][domain]=json.loads(path.read_text());assert not graphs[rev][domain].get('failed_sources')
        # Reuse exactly the III.8 normalizer statements, independent of oracles.
        original=(HERE.with_name('track-iii-008')/'build_index.py').read_text()
        start=original.index('        edges=[]');end=original.index("    query=load('queries.json')",start)
        block='\n'.join(line[8:] for line in original[start:end].splitlines())
        scope={'rows':rows,'rid':load('revisions.json')[rev]['id'],'graphs':graphs,'rev':rev,'indexes':indexes,'digest':source.digest}
        exec(compile(block,'iii8-normalizer-unchanged','exec'),scope)
    queries=load('queries.json');embed('queries',['query|'+q['id'] for q in queries],[q['text'] for q in queries],'personal')
    save(HERE/'evidence/indexes.json',indexes);save(HERE/'evidence/vectors.json',vectors)
    save(HERE/'evidence/graphify-raw.json',graphs);save(HERE/'evidence/embedding-requests.json',requests)
    print(json.dumps({'embedding_requests':len(requests),'vectors':len(vectors),'graphify_pin':collector.PIN}))


def packets():
    d=discover.Discovery();queries=load('queries.json')
    for variant,name in [('correct','results'),('stale-safe','stale-safe')]:
        raw=[d.query(d.binding,q,rev,mode,variant) for rev in ('A','B') for q in queries for mode in ('LEXICAL','COMBINED')]
        save(HERE/f'evidence/{name}.json',raw)
        result=selector.recover(variant)
        save(HERE/f'evidence/advisory-{name}.json',result)
    # Relevance cannot grant scope: retain global rankings internally for inspection.
    raw=[d.query(d.binding,q,'B','COMBINED','isolation') for q in queries]
    save(HERE/'evidence/protected-candidates.json',raw)
    print(json.dumps({'advisory_packets':24,'max_bytes':max(r['complete_bytes'] for r in result)}))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph-child',nargs=3);p.add_argument('--collect',action='store_true');p.add_argument('--packets',action='store_true');a=p.parse_args()
    if a.graph_child:collector.graph_child(*a.graph_child)
    if a.collect:collect()
    if a.packets:packets()

"""Real Graphify + local BGE indexing of frozen domain-separated synthetic sources."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from source import HERE,load,save,declarations,digest

UPSTREAM=Path('/home/leofuso/workspace/graphify-upstream')
PYTHON='/home/leofuso/workspace/blaine/experiments/graphify-carveout/.venv/bin/python'
PIN='b9cd9570728a5ff3485d2a1e36fe9a1272a368ae'


def graph_child(rev,domain,out):
    # No network/model call in Graphify; isolated fresh output/cache only.
    sys.path.insert(0,str(UPSTREAM));from graphify.extract import extract
    root=(HERE/'workspace'/rev).resolve();paths=sorted((root/domain).rglob('*.py'))
    with tempfile.TemporaryDirectory(prefix='blaine-iii8-graph-') as work:
        os.environ['GRAPHIFY_OUT']=str(Path(work)/'out')
        result=extract(paths,root=root,cache_root=Path(work),parallel=False)
    save(Path(out),result)


def main():
    p=argparse.ArgumentParser();p.add_argument('--graph-child',nargs=3);p.add_argument('--live',action='store_true');args=p.parse_args()
    if args.graph_child:return graph_child(*args.graph_child)
    assert args.live
    assert not (HERE/'evidence/indexes.json').exists(),'Do not overwrite frozen index evidence.'
    assert subprocess.check_output(['git','-C',str(UPSTREAM),'rev-parse','HEAD'],text=True).strip()==PIN
    assert not subprocess.check_output(['git','-C',str(UPSTREAM),'status','--porcelain'],text=True).strip()
    tracked=['queries.json','oracles.json','protocol.json','security.json','revisions.json','source.py','build_index.py','discover.py']
    registration={'frozen_at_utc':datetime.now(timezone.utc).isoformat(),'source_sha256':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in tracked},'graphify_pin':PIN,'prior_comparative_runs':0}
    save(HERE/'evidence/preregistration.json',registration)
    # Reuse existing loopback service client; no new inference transport or service.
    sys.path.insert(0,str(HERE.parents[1]/'infra/inference'));from accept import request
    inventory=request(8001,'/v1/models',timeout=10);save(HERE/'evidence/embedding-model.json',inventory)
    assert 'BAAI/bge-m3' in [x['id'] for x in inventory['data']]
    indexes={};vectors={};requests=[];graphs={}
    for rev in ('A','B'):
        rows=declarations(rev);rid=load('revisions.json')[rev]['id'];graphs[rev]={}
        for domain in ('personal','employer-x'):
            # Each provider batch contains one trusted domain only.
            batch=[r for r in rows.values() if r['file'].startswith(domain+'/')]
            body={'model':'BAAI/bge-m3','input':[r['text'] for r in batch]}
            response=request(8001,'/v1/embeddings',body,timeout=60)
            assert len(response['data'])==len(batch)
            requests.append({'revision':rev,'domain':domain,'input_ids':[r['target'] for r in batch],'input_sha256':digest(body),'model':response['model'],'usage':response.get('usage')})
            for value in response['data']:
                assert len(value['embedding'])==1024
                vectors[rev+'|'+batch[value['index']]['target']]=value['embedding']
            with tempfile.TemporaryDirectory(prefix='blaine-iii8-extract-') as temp:
                target=Path(temp)/'graph.json'
                env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(HERE.parents[1]/'experiments/graphify-carveout/offline'),'GRAPHIFY_QUERY_LOG_DISABLE':'1','GRAPHIFY_OUT':str(Path(temp)/'out')}
                run=subprocess.run([PYTHON,str(HERE/'build_index.py'),'--graph-child',rev,domain,str(target)],env=env,capture_output=True,text=True,timeout=40)
                assert run.returncode==0,run.stderr
                graph=json.loads(target.read_text());assert not graph.get('failed_sources')
                graphs[rev][domain]=graph
        edges=[]
        # Normalize real Graphify edges to our top-level declaration targets.
        for domain,graph in graphs[rev].items():
            nodes={n['id']:n for n in graph['nodes']}
            def target(n):
                if not n:return None
                candidates=[r for r in rows.values() if r['file']==n.get('source_file')]
                line=int((n.get('source_location') or 'L0').split('-')[0].lstrip('L'))
                return next((r['target'] for r in candidates if r['symbol']==n['label'].removesuffix('()').lstrip('.')),None) or next((r['target'] for r in candidates if r['line']<=line<=r['end_line']),None)
            for e in graph['edges']:
                kind=e.get('relation')
                if kind not in ('calls','inherits','imports_from'):continue
                a=target(nodes.get(e['source']));b=target(nodes.get(e['target']))
                if kind=='imports_from':
                    src=nodes.get(e['source'],{}).get('source_file');dest=nodes.get(e['target'],{}).get('source_file')
                    for x in rows.values():
                        if x['file']==src:
                            for y in rows.values():
                                if y['file']==dest and y['symbol'] in x['imports']:edges.append({'source':x['target'],'target':y['target'],'relation':'imports','origin':'graphify+source-import-resolution'})
                elif a and b and a!=b:edges.append({'source':a,'target':b,'relation':kind,'origin':'graphify'})
        unique={digest(e):e for e in edges}
        indexes[rev]={'revision':rid,'rows':rows,'edges':sorted(unique.values(),key=lambda e:(e['source'],e['target'],e['relation']))}
    query=load('queries.json');body={'model':'BAAI/bge-m3','input':[q['text'] for q in query]};response=request(8001,'/v1/embeddings',body,timeout=60)
    requests.append({'domain':'personal','input_ids':[q['id'] for q in query],'input_sha256':digest(body),'model':response['model'],'usage':response.get('usage')})
    for v in response['data']:vectors['query|'+query[v['index']]['id']]=v['embedding']
    save(HERE/'evidence/indexes.json',indexes);save(HERE/'evidence/vectors.json',vectors);save(HERE/'evidence/graphify-raw.json',graphs);save(HERE/'evidence/embedding-requests.json',requests)
    print(json.dumps({'status':'COLLECTED','embedding_requests':len(requests),'vectors':len(vectors),'graphify_pin':PIN}))


if __name__=='__main__':main()

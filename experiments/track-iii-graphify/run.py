"""Run only the frozen III.G retrieval comparison and isolated controls."""
from collections import Counter
import copy
import gzip
import hashlib
import json
from pathlib import Path
import time
from source import HERE,load,save,wire
from discover import Corpus,readgz,triple


def primary():
    queries=load(HERE/'queries.json');out=[];validations={}
    for repo in sorted({q['repo'] for q in queries}):
        start=time.perf_counter();c=Corpus(repo)
        validations[repo]=dict(construction_seconds=time.perf_counter()-start,
            source_validation=c.validation_setup,decisions=c.validation,
            counters=dict(Counter((e['confidence']+'/'+e['reason']) for e in c.validation)))
        for q in queries:
            if q['repo']!=repo:continue
            lex=c.lexical(q);graph=c.graph(q)
            for condition in ['A','B','C']:out.append(c.query(q,condition,lex,graph))
    save(HERE/'evidence/results.json',out)
    save(HERE/'evidence/validation.json',validations)


def controls():
    f=load(HERE/'controls.json');refresh=[]
    for q in f['freshness']:
        repo=q['repo'];a=Corpus(repo,'A','A');b=Corpus(repo,'B','B');stale=Corpus(repo,'A','B','stale');safe=Corpus(repo,'A','B')
        packets={}
        for name,c in [('A',a),('B',b),('stale',stale),('stale_safe',safe)]:
            result=c.query(q,'B',lex=([],dict(requests=0,source_files_opened=[])),graph=c.graph(q));packets[name]=result
        old={triple(e) for e in a.normalized};new={triple(e) for e in b.normalized}
        a_source={triple(e) for e in a.facts['edges']};b_source={triple(e) for e in b.facts['edges']}
        # Independent source delta, alongside the derived graph delta.
        refresh.append(dict(repo=repo,query=q,results=packets,removed_graph_edges=sorted(old-new),
            new_graph_edges=sorted(new-old),removed_source_edges=sorted(a_source-b_source),
            new_source_edges=sorted(b_source-a_source)))
    save(HERE/'evidence/freshness.json',refresh)
    q={k:v for k,v in f['inferred_trust'].items() if k not in ('raw_edge_index','expected_required','witness')}
    mutations={}
    for name,variant in [('correct','normal'),('unsafe','inferred-authority')]:
        c=Corpus(q['repo'],variant=variant)
        mutations[name]=c.query(q,'B',lex=([],dict(requests=0,source_files_opened=[])),graph=c.graph(q))
    mutations['query']=q;mutations['actual_raw_edge']=c.raw['edges'][f['inferred_trust']['raw_edge_index']]
    save(HERE/'evidence/inferred-mutation.json',mutations)
    # Actual security-filter mutation, using the frozen relevant impact neighborhood.
    q=next(q for q in load(HERE/'queries.json') if q['id']=='S-I1')
    c=Corpus(q['repo'],variant='isolation')
    save(HERE/'evidence/isolation-mutation.json',c.query(q,'B',lex=([],dict(requests=0,source_files_opened=[])),graph=c.graph(q)))


def main():
    frozen=load(HERE/'evidence/corpus-freeze.json')
    assert all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==v for n,v in frozen['sha256'].items()),'Frozen corpus changed'
    assert not (HERE/'evidence/results.json').exists(),'Do not overwrite completed comparison'
    primary();controls()
    print('Retained comparison and controls; use independent checker for gate decision.')


if __name__=='__main__':main()

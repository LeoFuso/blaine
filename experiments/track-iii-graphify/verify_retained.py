"""Post-evaluation integrity/reproduction checks. Does not overwrite primary evidence."""
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from source import HERE,inventory,load,save,wire


def main():
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    controls=[]
    for mode in ['stale','inferred','isolation']:
        out=HERE/'evidence'/('check-'+mode+'.json')
        cmd=[sys.executable,str(HERE/'check.py'),'--control',mode,'--output',str(out)]
        p=subprocess.run(cmd,capture_output=True,text=True,env=env)
        report=load(out)
        controls.append(dict(mode=mode,command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,
                             actual_violation=report['actual_violation'],status=report['status'],
                             mandatory=mode!='isolation'))
    save(HERE/'evidence/mutation-controls.json',controls)
    checks=[]
    def check(name,ok):checks.append(dict(check=name,ok=bool(ok)))
    for c in controls:
        if c['mandatory']:check(c['mode']+' actual leak and nonzero exit',c['exit_code']==1 and c['actual_violation'])
    for repo in load(HERE/'repositories.json'):
        for rev in ['A','B']:
            d=HERE/'evidence/indexes'/repo/rev
            with tempfile.TemporaryDirectory(prefix='iii-g-source-') as root:
                with tarfile.open(d/'source.tar.gz') as archive:archive.extractall(root,filter='data')
                actual=inventory(root,repo);expected=json.loads(gzip.decompress((d/'source.json.gz').read_bytes()))
                check('source facts reproducible '+repo+rev,wire(actual)==wire(expected))
    from discover import Corpus
    expected={(r['query'],r['condition']):r for r in load(HERE/'evidence/results.json')}
    queries=load(HERE/'queries.json');reproduced=[]
    for repo in sorted({q['repo'] for q in queries}):
        corpus=Corpus(repo)
        for q in queries:
            if q['repo']!=repo:continue
            lexical=corpus.lexical(q);graph=corpus.graph(q)
            for condition in ['A','B','C']:
                row=corpus.query(q,condition,lexical,graph);old=expected[q['id'],condition]
                check('identical packet '+q['id']+condition,wire(row['packet'])==wire(old['packet']))
                check('identical answers '+q['id']+condition,wire(row['candidate_answers'])==wire(old['candidate_answers']))
                reproduced.append(dict(query=q['id'],condition=condition,packet_sha256=hashlib.sha256(wire(row['packet']).encode()).hexdigest()))
    check('primary result never overwritten',hashlib.sha256((HERE/'evidence/results.json').read_bytes()).hexdigest()==load(HERE/'evidence/execution-errata.json')['completed_results_sha256'])
    save(HERE/'evidence/reproduction.json',dict(status='PASS' if all(c['ok'] for c in checks) else 'FAIL',checks=checks,packets=reproduced,
         notes='One deterministic verification replay; original primary evidence retained. Latencies are measured, not asserted byte-identical. Source facts independently re-derived from retained unmodified archives.'))
    print('reproduction',all(c['ok'] for c in checks),len(checks))
    return 0 if all(c['ok'] for c in checks) else 1


if __name__=='__main__':sys.exit(main())

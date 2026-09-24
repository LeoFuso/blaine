"""Independent aggregate verification, including actual nonzero mutation checks."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from check import evaluate, load, digest
D=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    e=D/'evidence'; primary=evaluate(e/'primary'); failures=list(primary['failures'])
    controls=[]
    for mode,case,leak in [('serialized-scope','A2','protected-root'),
                           ('stale-policy','B2','old-rule'),
                           ('serialized-provenance','A3',None)]:
        directory=e/mode
        report=evaluate(directory)
        proc=subprocess.run([sys.executable,str(D/'check.py'),str(directory)],capture_output=True,text=True)
        c=next(c for c in load(directory/'results.json')['cases'] if c['id']==case)
        rows=next(p for p in c['phases'] if p['stage']=='received')['export']['response']['entries']
        actual=(any(r['id']==leak for r in rows) and bool(report['forbidden_content_hits'])
                and bool(report['forbidden_metadata_hits'])) if leak else (
                    any(r['id']=='failure' and r['semantic_status']=='VERIFIED_SUCCESS' for r in rows)
                    and any(r['id']=='observation' and r['provenance']=='USER_DECLARATION' for r in rows))
        valid=proc.returncode==1 and report['status']=='FAIL' and actual and not proc.stderr
        if not valid: failures.append(mode+' did not cause actual caught violation')
        controls.append(dict(mutation=mode,checker_exit=proc.returncode,actual_violation=actual,
                             failed_checks=len(report['failures']),
                             content_leaks=len(report['forbidden_content_hits']),
                             metadata_leaks=len(report['forbidden_metadata_hits'])))
    reproduction=load(e/'reproducibility.json')
    if not all(row['checker_exit']==0 and row['runner_exit']==0 and all(row['byte_identical'].values())
               and all(digest(e/'primary'/name)==value for name,value in row['sha256'].items())
               for row in reproduction['runs']):
        failures.append('Default restoration/reproduction failed')
    summary=dict(status='PASS' if not failures else 'FAIL',failures=failures,
                 primary=primary,mutation_controls=controls,
                 corpus_sha256=load(e/'fixture-freeze.json')['sha256']['cases.json'],
                 history_unchanged=not any('source hash' in f for f in failures),
                 production_integration=False,subsequent_increment_started=False)
    raw=json.dumps(summary,indent=2,sort_keys=True)+'\n'
    if args.output: args.output.write_text(raw)
    else: print(raw,end='')
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__': sys.exit(main())

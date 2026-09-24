"""One retained evaluation; refuses overwrite. Reproduction uses a new directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    assert not (output/'results.json').exists(), 'Refuse to overwrite evaluated results'
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'}
    controls={}
    for variant in ('correct','stale-safe','freshness','isolation','fallback'):
        name='results' if variant=='correct' else variant
        path=output/(name+'.json')
        subprocess.run([sys.executable,str(HERE/'recover.py'),'--variant',variant,'--output',str(path)],check=True,env=env)
        report=output/(name+'-verification.json')
        cmd=[sys.executable,str(HERE/'check.py'),str(path),'--output',str(report)]
        if variant!='correct':cmd.append('--control')
        result=subprocess.run(cmd,capture_output=True,text=True,env=env)
        assert result.returncode in (0,1) and report.exists(),result.stderr
        controls[variant]={'exit_code':result.returncode,'report':json.loads(report.read_text())}
    # Default output after all mutations must exactly match the first result.
    restored=output/'restored.json'
    subprocess.run([sys.executable,str(HERE/'recover.py'),'--output',str(restored)],check=True,env=env)
    restored_equal=restored.read_bytes()==(output/'results.json').read_bytes()
    checks={
        'freshness_mutation_caught':controls['freshness']['exit_code']==1 and bool(controls['freshness']['report']['stale']),
        'isolation_mutation_caught':controls['isolation']['exit_code']==1 and bool(controls['isolation']['report']['forbidden']),
        'fallback_mutation_caught':controls['fallback']['exit_code']==1 and any(x.startswith('exact-retention/B/') for x in controls['fallback']['report']['failed']),
        'safe_fallback':controls['stale-safe']['exit_code']==0,
        'restored_equal':restored_equal}
    public={k:{'exit_code':v['exit_code'],'failed':v['report']['failed'],'stale':len(v['report']['stale']),'forbidden':len(v['report']['forbidden'])} for k,v in controls.items()}
    (output/'controls.json').write_text(json.dumps({'checks':checks,'controls':public},indent=2,sort_keys=True)+'\n')
    result=controls['correct']['report']
    summary={'status':'PASS' if result['status']=='PASS' and all(checks.values()) else 'FAIL','III_8_status':'FAIL','III_9_started':False,
             'aggregate':result['aggregate'],'max_complete_bytes':result['max_complete_bytes'],'stale':len(result['stale']),'forbidden':len(result['forbidden']),
             'controls':checks,'canonical':result['canonical'],'ranking_adjustments_after_outcomes':0,'model_calls':0,'task_submitted':False,
             'structural_incremental_utility':'UNPROVEN' if all(not x['groups']['STRUCTURAL']['unique_gains'] for x in result['aggregate']) else 'OBSERVED'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2))
    return int(summary['status']!='PASS')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'evidence');a=p.parse_args()
    raise SystemExit(run(a.output.resolve()))

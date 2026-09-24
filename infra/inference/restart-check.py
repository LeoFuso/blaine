#!/usr/bin/env python3
"""Controlled service recovery using the installed user units, never a duplicate."""
import json
import argparse
from pathlib import Path
import subprocess
import time
from accept import request, chat, embeddings

root = Path(__file__).resolve().parents[2]
path = root/'experiments/d1-service-adoption/evidence/inference-restarts.json'
p=argparse.ArgumentParser()
p.add_argument('--combined-only',action='store_true',help='Resume the combined-start check after retained individual restart evidence')
args=p.parse_args()
out = json.loads(path.read_text()) if args.combined_only else {'status':'RUNNING','checks':[]}
if args.combined_only:
    assert [x['unit'] for x in out['checks']]==['generation','embedding']
    out['maintenance_start_limit_reset']=True
def save(): path.write_text(json.dumps(out,indent=2)+'\n')
def identity(name):
    raw=subprocess.check_output(['systemctl','--user','show','blaine-'+name,
        '-p','MainPID','-p','InvocationID','-p','ActiveState','-p','UnitFileState'],text=True)
    return dict(line.split('=',1) for line in raw.splitlines())
def functional():
    assert request(8000,'/health')['http_status']==200
    assert request(8001,'/health')['http_status']==200
    result=chat('Return exactly RESTART_READY.')
    assert result['content'].strip()=='RESTART_READY'
    return {'generation':result,'embeddings':embeddings()}
save()
for name, other in ([] if args.combined_only else [('generation','embedding'),('embedding','generation')]):
    before, peer = identity(name), identity(other)
    start=time.monotonic()
    subprocess.run(['systemctl','--user','restart','blaine-'+name],check=True,timeout=240)
    after=identity(name)
    assert after['ActiveState']=='active' and after['UnitFileState']=='enabled'
    assert before['InvocationID']!=after['InvocationID']
    assert identity(other)['InvocationID']==peer['InvocationID']
    out['checks'].append({'unit':name,'before':before,'after':after,'peer_unchanged':True,
                          'restart_seconds':round(time.monotonic()-start,3),'functional':functional()});save()
# Regression for the observed global-VRAM profiling race at simultaneous startup.
subprocess.run(['systemctl','--user','stop','blaine-generation','blaine-embedding'],check=True,timeout=90)
subprocess.run(['systemctl','--user','start','blaine-generation'],check=True,timeout=240)
out['combined_start']={'generation':identity('generation'),'embedding':identity('embedding'),
                       'functional':functional()}
out['status']='PASS';save()
print('PASS: generation restart, embedding restart, and ordered combined start')

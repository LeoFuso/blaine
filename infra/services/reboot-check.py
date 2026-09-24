#!/usr/bin/env python3
"""Read-only D1.G check. Never starts services, creates fixtures or reboots."""
import argparse,datetime,hashlib,json,runpy,subprocess,sys,urllib.request
from pathlib import Path
from urllib.parse import urlencode

root=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser()
p.add_argument('--after-reboot',action='store_true')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args(); evidence=root/'experiments/d1-service-adoption/evidence'
def read(name):return json.loads((evidence/(name+'.json')).read_text())
def http(url,body=None,headers=None):
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json',**(headers or {})})
 with urllib.request.urlopen(req,timeout=20) as response:
  raw=response.read();return json.loads(raw) if raw else None

def state(task):
 req=urllib.request.Request('http://127.0.0.1:48080/CognitiveTaskV1/'+task+'/inspect',method='POST')
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)

def cmd(args):return subprocess.check_output(args,text=True).strip()

report={'status':'INCOMPLETE','scope':'post-reboot' if a.after_reboot else 'pre-reboot',
        'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'checks':{}}
try:
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip();report['boot_id']=boot
 if a.after_reboot:
  assert boot!=read('pre-reboot')['boot_id'],'No reboot occurred'
  subprocess.run([sys.executable,str(root/'infra/services/wait-ready.py'),'--timeout','1500',
    'http://127.0.0.1:8000/health','http://127.0.0.1:8001/health','http://127.0.0.1:8531/health','http://127.0.0.1:49070/deployments'],check=True,timeout=1510)
 assert cmd(['loginctl','show-user','leofuso','-p','Linger'])=='Linger=yes'
 units=['docker','blaine-infra','blaine-generation','blaine-embedding','blaine-mirix','blaine-restate','blaine-runtime']
 for name in units:
  assert cmd(['systemctl','--user','is-enabled',name+'.service'])=='enabled',name
  assert cmd(['systemctl','--user','is-active',name+'.service'])=='active',name
 for name in ['postgresql@18-main','redis-server','alloy']:
  assert cmd(['systemctl','is-active',name+'.service'])=='active',name
 report['checks']['enabled_user_services_and_native_readiness']='PASS'
 for port,model in [(8000,'nvidia/Qwen3.8-27B-NVFP4'),(8001,'BAAI/bge-m3')]:
  http(f'http://127.0.0.1:{port}/health')
  models=http(f'http://127.0.0.1:{port}/v1/models');assert models['data'][0]['id']==model
 http('http://127.0.0.1:8531/health')
 deployments=http('http://127.0.0.1:49070/deployments')['deployments']
 assert any(d['uri']=='http://127.0.0.1:49080/' and any(s['name']=='CognitiveTaskV1' for s in d['services']) for d in deployments)
 report['checks']['readiness_models_and_deployment']='PASS'
 cids=cmd(['docker','--context','rootless','ps','-q','--filter','label=com.docker.compose.project=blaine-infra-rootless']).split()
 assert len(cids)==4
 assert all(cmd(['docker','--context','rootless','inspect','--format','{{.State.Health.Status}}',cid])=='healthy' for cid in cids)
 report['checks']['four_rootless_containers_healthy']='PASS'
 Services=runpy.run_path(str(root/'infra/rootless/accept-services.py'))['Services']
 client=Services(Path.home()/'.config/blaine/secrets');client.health()
 f=read('object-fixture');body=client.s3('blaine').get_object(Bucket=f['bucket'],Key=f['key'])['Body'].read()
 assert hashlib.sha256(body).hexdigest()==f['sha256'] and body.decode()==f['content']
 report['checks']['same_object_hash']={'bucket':f['bucket'],'key':f['key'],'sha256':f['sha256']}
 f=read('mirix-fixture');query={'user_id':f['user_id'],'query':f['project']+' release marker','memory_type':'semantic','search_field':'details','search_method':'embedding','limit':5,'filter_tags':json.dumps(f['tags']),'similarity_threshold':0.5}
 rows=http('http://127.0.0.1:8531/memory/search?'+urlencode(query),headers={'x-client-id':f['client_id']})['results']
 rows=[r for r in rows if f['marker'] in json.dumps(r)]
 assert sorted(r['id'] for r in rows)==sorted(f['memory_ids'])
 normalized=sorted([{k:r.get(k) for k in ['id','name','summary','details','source']} for r in rows],key=lambda r:r['id'])
 assert hashlib.sha256(json.dumps(normalized,sort_keys=True).encode()).hexdigest()==read('mirix-restart')['content_sha256']
 report['checks']['same_semantic_memory']=f['memory_ids']
 f=read('durable-fixture')
 assert state(f['tasks']['waiting'])==read('durable-waiting-before')
 assert state(f['tasks']['resume'])==read('durable-resumed-completed')
 assert state(f['tasks']['small'])==read('durable-small')
 for task,expected in read('restate-retained-legacy-tasks').items():assert state(task)==expected
 assert state(read('cognition-summary')['task_id'])==read('cognition-state')
 for label,task in [('durable-artifact',f['tasks']['small']),('cognition-artifact',read('cognition-summary')['task_id'])]:
  actual=http('http://127.0.0.1:48080/CognitiveTaskV1/'+task+'/artifact',{'name':'answer'})
  assert actual==read(label)
 memory_inventory=a.output.with_name(a.output.stem+'-mirix.json')
 subprocess.run([str(Path.home()/'workspace/mirix/.venv/bin/python'),str(root/'infra/services/mirix-state.py'),str(memory_inventory)],check=True)
 current=json.loads(memory_inventory.read_text()); original=read('mirix-before')
 assert current['database']==original['database']
 indexed={r['id']:r for r in current['semantic_memories']}
 assert all(indexed[r['id']]==r for r in original['semantic_memories'])
 report['checks']['original_memories_and_artifact_bytes']='PASS'
 report['checks']['same_durable_tasks_and_wait']=f['tasks']
 ownership=a.output.with_name(a.output.stem+'-processes.json')
 subprocess.run([sys.executable,str(root/'infra/services/process-ownership.py'),str(ownership)],check=True)
 roles=json.loads(ownership.read_text())['processes']
 for role in ['mirix','restate','blaine']:assert sum(role in r['roles'] for r in roles)==1
 for kind in ['generation','embedding']:
  assert any('blaine-'+kind+'.service' in r['cgroup'] for r in roles)
 assert not http('http://127.0.0.1:11434/api/ps')['models']
 report['checks']['no_duplicate_runtime_or_terminal_owner']='PASS'
 for verb,expected in [('is-enabled','disabled'),('is-active','inactive')]:
  r=subprocess.run(['systemctl',verb,'blaine-partial-backup.timer'],text=True,capture_output=True)
  assert r.stdout.strip()==expected
 report['checks']['backup']='PAUSED; timer disabled/inactive'
 report['gpu']=cmd(['nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader'])
 if a.after_reboot:
  smoke=a.output.with_name(a.output.stem+'-inference.json')
  subprocess.run([sys.executable,str(root/'infra/inference/accept.py'),'--output',str(smoke)],check=True,timeout=180)
  assert json.loads(smoke.read_text())['status']=='PASS'
  report['checks']['generation_json_tools_embeddings_coexistence']='PASS'
 report['status']='PASS'
except Exception as error:
 report['status']='STOP';report['failure_type']=type(error).__name__
 raise
finally:
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps(report,indent=2)+'\n')
 print('D1.G',report['scope'],report['status'],flush=True)

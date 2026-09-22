#!/usr/bin/env python3
"""Bounded real-service offline check; no Cloud credentials or second collector.
Run once as root from repository. Always restore byte-identical local config.
"""
import hashlib,json,os,subprocess,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'experiments/d1-grafana-cloud-data-plane/evidence/offline.json'
ACTIVE=Path('/etc/alloy/config.alloy')
WAL=Path('/var/lib/alloy/data/prometheus.remote_write.grafana_metrics/wal')
UNITS=['blaine-generation','blaine-embedding','blaine-mirix','blaine-restate','blaine-runtime']
def run(*args):
    return subprocess.run(args,capture_output=True,text=True,check=True,timeout=45).stdout.strip()
def now():return datetime.now(timezone.utc).isoformat()
def pids():
    return {u:run('runuser','-u','leofuso','--','env','XDG_RUNTIME_DIR=/run/user/1000','systemctl','--user','show',u,'-p','MainPID','--value') for u in UNITS}
def ready():
    with urlopen('http://127.0.0.1:12345/-/ready',timeout=5) as r:return r.status==200
def counters():
    with urlopen('http://127.0.0.1:12345/metrics',timeout=5) as r:lines=r.read().decode().splitlines()
    return [x for x in lines if not x.startswith('#') and ('prometheus_remote_storage_' in x or 'prometheus_wal_' in x) and 'grafana_metrics' in x]
def wal():
    return {'path':str(WAL),'bytes':sum(p.stat().st_size for p in WAL.rglob('*') if p.is_file()),'sample_stats':run('alloy','tools','prometheus.remote_write','sample-stats','--selector','blaine_d1_cloud_delivery_test',str(WAL))}
assert os.geteuid()==0
original=ACTIVE.read_bytes()
assert original==(ROOT/'infra/alloy/config.alloy').read_bytes(),'Refuse replacing an unrecognized live configuration'
assert not OUT.exists(),'Do not overwrite prior evidence'
report={'status':'INCOMPLETE','started':now(),'run_id':'offline-'+uuid.uuid4().hex,'version':run('alloy','--version'),'original_sha256':hashlib.sha256(original).hexdigest(),'cloud_credentials_used':False,'cloud_delivery':'NOT TESTED','units_before':pids()}
fragment=(ROOT/'infra/alloy/metrics.alloy.inactive').read_text()
fragment=fragment.replace('"https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/push"','"http://127.0.0.1:1/api/prom/push"')
fragment=fragment.replace('    basic_auth {\n      username = "3602220"\n      password = sys.env("GRAFANA_CLOUD_METRICS_API_KEY")\n    }\n','')
base=original.decode().replace('[otelcol.receiver.prometheus.local.receiver]','[otelcol.receiver.prometheus.local.receiver, prometheus.remote_write.grafana_metrics.receiver, prometheus.relabel.delivery_test.receiver]')
synthetic='''
prometheus.relabel "delivery_test" {
  forward_to = [prometheus.remote_write.grafana_metrics.receiver]
  rule {
    source_labels = ["__name__"]
    regex = "alloy_build_info"
    action = "keep"
  }
  rule {
    target_label = "__name__"
    replacement = "blaine_d1_cloud_delivery_test"
  }
  rule {
    target_label = "run_id"
    replacement = "RUN_ID"
  }
}
'''.replace('RUN_ID',report['run_id'])
candidate=Path('/etc/alloy/blaine-metrics-offline.alloy')
try:
    candidate.write_text(base+'\n'+fragment+synthetic)
    run('alloy','validate','--stability.level=public-preview',str(candidate))
    report['config_validation']='PASS'
    os.replace(candidate,ACTIVE)
    report['outage_start']=now()
    run('systemctl','restart','alloy')
    time.sleep(8)
    report['offline_start_ready']=ready()
    print('Offline startup ready; collecting for 65 seconds.',flush=True)
    time.sleep(65)
    report['before_restart']={'ready':ready(),'wal':wal(),'counters':counters()}
    run('systemctl','restart','alloy')
    time.sleep(8)
    report['offline_restart_ready']=ready()
    print('Offline restart ready; checking retained samples.',flush=True)
    time.sleep(35)
    report['after_restart']={'ready':ready(),'wal':wal(),'counters':counters()}
    report['units_after']=pids()
    report['blaine_pids_unchanged']=report['units_before']==report['units_after']
    assert report['offline_start_ready'] and report['offline_restart_ready'] and report['blaine_pids_unchanged']
    assert 'blaine_d1_cloud_delivery_test' in report['before_restart']['wal']['sample_stats']
    assert 'blaine_d1_cloud_delivery_test' in report['after_restart']['wal']['sample_stats']
    report['status']='LOCAL OFFLINE CHECK PASS; CLOUD ACCEPTANCE BLOCKED'
finally:
    ACTIVE.write_bytes(original)
    candidate.unlink(missing_ok=True)
    run('systemctl','restart','alloy')
    time.sleep(8)
    report['restored_ready']=ready()
    report['restored_exact_config']=ACTIVE.read_bytes()==original
    report['ended']=now()
    report['outage_end']=report['ended']
    OUT.write_text(json.dumps(report,indent=2)+'\n')
    os.chown(OUT,1000,1000)
    print(json.dumps({k:report[k] for k in ['status','restored_ready','restored_exact_config','run_id']}),flush=True)

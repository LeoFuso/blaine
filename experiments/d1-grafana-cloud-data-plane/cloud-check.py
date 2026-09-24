#!/usr/bin/env python3
"""Single-service end-to-end acceptance, with bounded exporter-only proxy outage.
Requires the reviewed native metrics composition already activated. Root reads
only its protected local secret; values/headers never enter evidence or argv.
"""
import base64,hashlib,json,os,runpy,subprocess,time,uuid
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError
ROOT=Path(__file__).resolve().parents[2]
cloud=runpy.run_path(str(ROOT/'infra/grafana-cloud.py'))
ACTIVE=Path('/etc/alloy/config.alloy')
OUT=ROOT/'experiments/d1-grafana-cloud-data-plane/evidence/cloud.json'
WAL=Path('/var/lib/alloy/data/prometheus.remote_write.grafana_metrics/wal')
URL='https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/api/v1/query'
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
http=build_opener(NoRedirect)
def run(*args):return subprocess.run(args,capture_output=True,text=True,check=True,timeout=60).stdout.strip()
def readiness():
    with http.open('http://127.0.0.1:12345/-/ready',timeout=5) as r:return r.status==200
def query(expression):
    req=Request(URL+'?'+urlencode({'query':expression}),headers={'Authorization':authorization})
    try:
        with http.open(req,timeout=20) as response:
            data=json.load(response)
            assert data.get('status')=='success','Cloud query did not succeed'
            return data['data']['result']
    except HTTPError as exc:raise RuntimeError('Cloud query HTTP '+str(exc.code)) from None
    except URLError:raise RuntimeError('Cloud query transport unavailable') from None
def await_samples(selector,seconds=100):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        result=query(selector+'[15m]')
        if result:return result
        time.sleep(5)
    raise RuntimeError('Cloud sample readback deadline exceeded')
def snapshot():
    with http.open('http://127.0.0.1:12345/metrics',timeout=5) as r:lines=r.read().decode().splitlines()
    return {'ready':readiness(),'time':time.time(),'wal_bytes':sum(p.stat().st_size for p in WAL.rglob('*') if p.is_file()),
            'wal_synthetic':run('alloy','tools','prometheus.remote_write','sample-stats','--selector',selector,str(WAL)),
            'counters':[x for x in lines if not x.startswith('#') and (('prometheus_remote_storage_' in x and 'grafana_metrics' in x) or 'otelcol_exporter_sent_metric_points_total' in x)]}
def pids():
    return {u:run('runuser','-u','leofuso','--','env','XDG_RUNTIME_DIR=/run/user/1000','systemctl','--user','show',u,'-p','MainPID','--value') for u in ['blaine-generation','blaine-embedding','blaine-mirix','blaine-restate','blaine-runtime']}
def apply(phase,outage=False):
    text=original.replace('prometheus.remote_write.grafana_metrics.receiver]', 'prometheus.remote_write.grafana_metrics.receiver, prometheus.relabel.delivery_test.receiver]')
    text+=synthetic.replace('PHASE',phase)
    if outage:
        text=text.replace('    name = "grafana_metrics"','    name = "grafana_metrics"\n    proxy_url = "http://127.0.0.1:1"')
    candidate=Path('/etc/alloy/blaine-cloud-check.alloy')
    cloud['atomic'](candidate,text,0o644)
    r=subprocess.run(['alloy','validate','--stability.level=public-preview',str(candidate)],env=dict(os.environ,**values),capture_output=True)
    assert r.returncode==0,'Candidate validation failed; diagnostic output suppressed'
    os.replace(candidate,ACTIVE)
    run('systemctl','restart','alloy')
    time.sleep(5)
    assert readiness(),'Alloy not ready'

assert os.geteuid()==0
assert not OUT.exists(),'Do not overwrite evidence'
secret=cloud['METRICS_ENV_FILE']
assert secret.resolve()==secret and secret.stat().st_uid==0 and not secret.stat().st_mode & 0o077
values=cloud['validate_metrics'](dict(x.split('=',1) for x in secret.read_text().splitlines() if x))
authorization='Basic '+base64.b64encode(('3602220:'+values['GRAFANA_CLOUD_METRICS_API_KEY']).encode()).decode()
original=ACTIVE.read_text()
expected=cloud['compose_metrics'](Path('/etc/blaine/infra/alloy-local.alloy').read_text(),Path('/etc/blaine/infra/metrics.alloy.inactive').read_text())
assert original==expected,'Refuse unknown active metrics composition'
run_id='cloud-'+uuid.uuid4().hex
selector='blaine_d1_cloud_delivery_test{run_id="'+run_id+'"}'
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
  rule {
    target_label = "phase"
    replacement = "PHASE"
  }
}
'''.replace('RUN_ID',run_id)
report={'status':'INCOMPLETE','started':time.time(),'run_id':run_id,'query_endpoint':URL,'original_config_sha256':hashlib.sha256(original.encode()).hexdigest(),'units_before':pids()}
try:
    report['cloud_query_authentication']=bool(query('vector(1)'))
    print('Cloud query authentication passed.',flush=True)
    apply('connected')
    report['connected_samples']=await_samples(selector)
    report['connected_state']=snapshot()
    print('Unique metric visible upstream; starting exporter-only outage.',flush=True)
    report['outage_start']=time.time()
    apply('outage',True)
    report['offline_start_ready']=readiness()
    time.sleep(55)
    report['queued_before_restart']=snapshot()
    print('Pending WAL captured; restarting while exporter remains unreachable.',flush=True)
    run('systemctl','restart','alloy')
    time.sleep(5)
    report['offline_restart_ready']=readiness()
    time.sleep(35)
    report['queued_after_restart']=snapshot()
    outage_selector='blaine_d1_cloud_delivery_test{run_id="'+run_id+'",phase="outage"}'
    report['outage_samples_before_reconnect']=query(outage_selector+'[15m]')
    assert not report['outage_samples_before_reconnect'],'Outage samples escaped the test boundary'
    assert 'phase="outage"' in report['queued_after_restart']['wal_synthetic'],'No outage samples retained'
    report['outage_end']=time.time()
    apply('restored')
    print('Connectivity restored; awaiting Cloud readback of outage samples.',flush=True)
    report['replayed_outage_samples']=await_samples(outage_selector)
    timestamps=[float(v[0]) for series in report['replayed_outage_samples'] for v in series['values']]
    assert any(report['outage_start'] <= t <= report['outage_end'] for t in timestamps),'No actual outage-time sample upstream'
    assert any(report['outage_start'] <= t <= report['queued_before_restart']['time'] for t in timestamps),'Pre-restart outage sample did not replay'
    drain_deadline=time.monotonic()+60
    while True:
        state=snapshot()
        pending=[float(x.rsplit(' ',1)[1]) for x in state['counters'] if x.startswith('prometheus_remote_storage_samples_pending{')]
        if pending and sum(pending)==0:break
        if time.monotonic()>=drain_deadline:raise RuntimeError('Queue did not drain within deadline')
        time.sleep(3)
    report['recovered_state']=state
    report['cloud_scrape_health']=query('up{environment="blaine-dev",host="blaine"}')
    assert len(report['cloud_scrape_health']) >= 2 and all(float(s['value'][1])==1 for s in report['cloud_scrape_health']),'Host/self scrape regression'

    report['units_after']=pids()
    assert report['units_before']==report['units_after'],'Blaine PID changed'
    report['status']='PASS'
finally:
    cloud['atomic'](ACTIVE,original,0o644)
    Path('/etc/alloy/blaine-cloud-check.alloy').unlink(missing_ok=True)
    run('systemctl','restart','alloy')
    time.sleep(5)
    report['final_ready']=readiness()
    report['final_exact_metrics_config']=ACTIVE.read_text()==original
    report['ended']=time.time()
    OUT.write_text(json.dumps(report,indent=2)+'\n');os.chown(OUT,1000,1000)
    print(json.dumps({k:report[k] for k in ['status','run_id','final_ready','final_exact_metrics_config']}),flush=True)

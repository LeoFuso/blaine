#!/usr/bin/env python3
"""Bounded fixed-config network fault, using a temporary loopback CONNECT fixture.
No TLS interception, payload recording, extra collector or persistent proxy.
The exact remote-write config stays constant through outage/restart/recovery.
"""
import base64,json,os,runpy,select,socket,subprocess,threading,time,uuid
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[2]
m=runpy.run_path(str(ROOT/'infra/grafana-cloud.py'))
ACTIVE=Path('/etc/alloy/config.alloy')
OUT=ROOT/'experiments/d1-grafana-cloud-data-plane/evidence/transport.json'
DEST='prometheus-prod-40-prod-sa-east-1.grafana.net'
blocked=threading.Event()
class Proxy(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_CONNECT(self):
        if self.path!=DEST+':443':self.send_error(403);return
        if blocked.is_set():self.send_error(503);return
        try:upstream=socket.create_connection((DEST,443),timeout=10)
        except OSError:self.send_error(502);return
        with upstream:
            self.send_response(200);self.end_headers()
            peers=[self.connection,upstream]
            try:
                while not blocked.is_set():
                    readers,_,_=select.select(peers,[],[],0.2)
                    for peer in readers:
                        data=peer.recv(65536)
                        if not data:return
                        (upstream if peer is self.connection else self.connection).sendall(data)
            except OSError:pass
        self.close_connection=True
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
http=build_opener(NoRedirect)
def run(*args):return subprocess.run(args,capture_output=True,text=True,check=True,timeout=60).stdout.strip()
def ready():
    with http.open('http://127.0.0.1:12345/-/ready',timeout=5) as r:return r.status==200
def query(selector):
    req=Request('https://'+DEST+'/api/prom/api/v1/query?'+urlencode({'query':selector}),headers={'Authorization':authorization})
    with http.open(req,timeout=20) as r:data=json.load(r)
    assert data['status']=='success'
    return data['data']['result']
def samples():return query(selector+'[15m]')
def timestamps(rows):return [float(p[0]) for row in rows for p in row['values']]
def snapshot():
    wal=Path('/var/lib/alloy/data/prometheus.remote_write.grafana_metrics/wal')
    with http.open('http://127.0.0.1:12345/metrics',timeout=5) as r:lines=r.read().decode().splitlines()
    return {'time':time.time(),'ready':ready(),'wal_bytes':sum(x.stat().st_size for x in wal.rglob('*') if x.is_file()),'wal_synthetic':run('alloy','tools','prometheus.remote_write','sample-stats','--selector',selector,str(wal)),
            'counters':[x for x in lines if not x.startswith('#') and (('prometheus_remote_storage_' in x and 'grafana_metrics' in x) or 'otelcol_exporter_sent_metric_points_total' in x)]}
assert os.geteuid()==0 and not OUT.exists()
values=m['validate_metrics'](dict(x.split('=',1) for x in m['METRICS_ENV_FILE'].read_text().splitlines() if x))
authorization='Basic '+base64.b64encode(('3602220:'+values['GRAFANA_CLOUD_METRICS_API_KEY']).encode()).decode()
original=ACTIVE.read_text()
assert original==m['compose_metrics'](Path('/etc/blaine/infra/alloy-local.alloy').read_text(),Path('/etc/blaine/infra/metrics.alloy.inactive').read_text())
run_id='transport-'+uuid.uuid4().hex
selector='blaine_d1_cloud_delivery_test{run_id="'+run_id+'"}'
server=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
threading.Thread(target=server.serve_forever,daemon=True).start()
config=original.replace('    name = "grafana_metrics"','    name = "grafana_metrics"\n    proxy_url = "http://127.0.0.1:'+str(server.server_port)+'"')
config=config.replace('prometheus.remote_write.grafana_metrics.receiver]', 'prometheus.remote_write.grafana_metrics.receiver, prometheus.relabel.delivery_test.receiver]')
config+='''
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
'''.replace('RUN_ID',run_id)
report={'status':'INCOMPLETE','started':time.time(),'run_id':run_id,'fixed_remote_config_through_outage':True,'failure_fixture':'temporary loopback CONNECT proxy; pinned single destination; no TLS decryption, data recording or queue','proxy_port':server.server_port}
try:
    candidate=Path('/etc/alloy/blaine-transport-check.alloy');m['atomic'](candidate,config,0o644)
    validation=subprocess.run(['alloy','validate','--stability.level=public-preview',str(candidate)],env=dict(os.environ,**values),capture_output=True)
    assert validation.returncode==0
    os.replace(candidate,ACTIVE);run('systemctl','restart','alloy');time.sleep(5)
    deadline=time.monotonic()+90
    while True:
        rows=samples()
        if rows:break
        assert time.monotonic()<deadline,'Initial readback deadline exceeded'
        time.sleep(5)
    report['initial_samples']=rows
    print('Fixed-config synthetic metric visible; blocking only proxy transport.',flush=True)
    blocked.set();report['outage_start']=time.time()
    time.sleep(55)
    report['before_restart']=snapshot()
    report['restart_started']=time.time()
    print('Restarting same Alloy config with proxy transport still blocked.',flush=True)
    run('systemctl','restart','alloy');time.sleep(5)
    report['restart_completed']=time.time();report['offline_restart_ready']=ready()
    time.sleep(40)
    report['after_restart']=snapshot()
    report['cloud_before_recovery']=samples()
    assert not any(report['outage_start']+2<t<report['after_restart']['time'] for t in timestamps(report['cloud_before_recovery']))
    assert ACTIVE.read_text()==config,'Remote config changed during test'
    report['recovery_start']=time.time();blocked.clear()
    print('Transport restored without config change or restart; checking queued sample delivery.',flush=True)
    deadline=time.monotonic()+100
    while True:
        rows=samples();ts=timestamps(rows)
        if any(report['restart_completed']<t<report['recovery_start'] for t in ts):break
        assert time.monotonic()<deadline,'Post-restart outage samples did not arrive'
        time.sleep(5)
    report['cloud_after_recovery']=rows
    report['post_restart_outage_samples_replayed']=True
    report['pre_restart_outage_samples_replayed']=any(report['outage_start']+2<t<report['restart_started'] for t in ts)
    drain_deadline=time.monotonic()+60
    while True:
        state=snapshot()
        pending=[float(x.rsplit(' ',1)[1]) for x in state['counters'] if x.startswith('prometheus_remote_storage_samples_pending{')]
        if pending and sum(pending)==0:break
        assert time.monotonic()<drain_deadline,'Queue did not drain'
        time.sleep(3)
    report['recovered_state']=state
    report['cloud_scrape_health']=query('up{environment="blaine-dev",host="blaine"}')
    assert len(report['cloud_scrape_health'])>=2 and all(float(s['value'][1])==1 for s in report['cloud_scrape_health'])
    report['status']='PASS' if report['pre_restart_outage_samples_replayed'] else 'PARTIAL: live outage recovery PASS; pending pre-restart samples NOT replayed'
finally:
    blocked.clear()
    m['atomic'](ACTIVE,original,0o644)
    Path('/etc/alloy/blaine-transport-check.alloy').unlink(missing_ok=True)
    run('systemctl','restart','alloy');time.sleep(5)
    server.shutdown();server.server_close()
    report['final_ready']=ready();report['final_exact_metrics_config']=ACTIVE.read_text()==original
    report['ended']=time.time()
    OUT.write_text(json.dumps(report,indent=2)+'\n');os.chown(OUT,1000,1000)
    print(json.dumps({k:report[k] for k in ['status','run_id','final_ready','final_exact_metrics_config']}),flush=True)

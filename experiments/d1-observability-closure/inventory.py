#!/usr/bin/env python3
"""Read-only live observability inventory; never prints credentials or log bodies."""
import concurrent.futures,hashlib,json,os,re,runpy,subprocess,time
from collections import Counter
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'experiments/d1-observability-closure/evidence'
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*a,**k):return None
http=build_opener(NoRedirect)
m=runpy.run_path(str(ROOT/'infra/grafana-cloud.py'));p=m['METRICS_ENV_FILE']
assert p.stat().st_uid==0 and not p.stat().st_mode&0o077
v=m['validate_metrics'](dict(x.split('=',1) for x in p.read_text().splitlines() if x))
import base64
auth='Basic '+base64.b64encode(('3602220:'+v['GRAFANA_CLOUD_METRICS_API_KEY']).encode()).decode()
S='environment="blaine-dev",host="blaine"'
queries={
 'cpu_percent':'100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{'+S+',mode="idle"}[5m])))',
 'cpu_by_core_percent':'100 * (1 - avg by (instance,cpu) (rate(node_cpu_seconds_total{'+S+',mode="idle"}[5m])))',
 'load_1m':'node_load1{'+S+'}',
 'load_5m':'node_load5{'+S+'}',
 'load_15m':'node_load15{'+S+'}',
 'memory_used_percent':'100 * (1 - node_memory_MemAvailable_bytes{'+S+'} / node_memory_MemTotal_bytes{'+S+'})',
 'memory_available_bytes':'node_memory_MemAvailable_bytes{'+S+'}',
 'swap_used_bytes':'node_memory_SwapTotal_bytes{'+S+'} - node_memory_SwapFree_bytes{'+S+'}',
 'filesystem_used_percent':'100 * (1 - node_filesystem_avail_bytes{'+S+',fstype!~"tmpfs|devtmpfs|overlay|squashfs"} / node_filesystem_size_bytes{'+S+',fstype!~"tmpfs|devtmpfs|overlay|squashfs"})',
 'filesystem_available_bytes':'node_filesystem_avail_bytes{'+S+',fstype!~"tmpfs|devtmpfs|overlay|squashfs"}',
 'disk_read_bytes_per_second':'rate(node_disk_read_bytes_total{'+S+',device=~"nvme.*|sd[a-z]+"}[5m])',
 'disk_write_bytes_per_second':'rate(node_disk_written_bytes_total{'+S+',device=~"nvme.*|sd[a-z]+"}[5m])',
 'network_receive_bytes_per_second':'rate(node_network_receive_bytes_total{'+S+',device!="lo"}[5m])',
 'network_transmit_bytes_per_second':'rate(node_network_transmit_bytes_total{'+S+',device!="lo"}[5m])',
 'systemd_failed_count':'sum(node_systemd_unit_state{'+S+',state="failed"})',
 'systemd_failed_units':'node_systemd_unit_state{'+S+',state="failed"} == 1',
 'systemd_service_active':'node_systemd_unit_state{'+S+',name=~"alloy.service|postgresql.*|redis.*|user@1000.service",state="active"}',
 'blaine_user_service_series':'node_systemd_unit_state{'+S+',name=~"blaine-(generation|embedding|mirix|restate|runtime).service"}',
 'gpu_series':'count by (__name__) ({__name__=~"(?i).*(dcgm|nvidia|gpu|cuda|nvml).*"})',
 'vllm_cloud_series':'count by (__name__) ({__name__=~"vllm:.*"})',
 'cloud_scrape_health':'up{'+S+'}',
 'host_metric_names':'count by (__name__) ({'+S+',job="integrations/unix"})',
}
def query(item):
 key,q=item
 try:
  request=Request('https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/api/v1/query?'+urlencode({'query':q}),headers={'Authorization':auth})
  with http.open(request,timeout=30) as r:data=json.load(r)
  rows=data.get('data',{}).get('result',[])
  return key,{'query':q,'status':data.get('status'),'series_count':len(rows),'result':rows}
 except Exception as e:return key,{'query':q,'error_type':type(e).__name__}
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=dict(pool.map(query,queries.items()))
report={'observed_at':time.time(),'queries':results}
(OUT/'cloud-queries.json').write_text(json.dumps(report,indent=2)+'\n')
for k,v in results.items():print(k,v.get('status',v.get('error_type')),v.get('series_count'),json.dumps(v.get('result',[])[:2])[:650])
config=Path('/etc/alloy/config.alloy').read_text()
with http.open('http://127.0.0.1:12345/metrics',timeout=10) as r:local=r.read().decode()
report={'observed_at':time.time(),'active_config_sha256':hashlib.sha256(config.encode()).hexdigest(),
 'scrapes':re.findall(r'prometheus.scrape "([^"]+)"',config),'exporters':re.findall(r'(?:otelcol.exporter|prometheus.remote_write|loki.write)\.[a-z_]*\s*"[^"]+"|prometheus.remote_write "[^"]+"',config),
 'journal_unit_filters':re.findall(r'  matches = "([^"]+)"',config),
 'otlp_receivers':['grpc 127.0.0.1:4317','http 127.0.0.1:4318'],
 'pipeline_counters':[x for x in local.splitlines() if not x.startswith('#') and any(s in x for s in ['otelcol_receiver_accepted_spans','otelcol_exporter_sent_spans','otelcol_receiver_accepted_log_records','otelcol_exporter_sent_log_records','loki_source_journal_target_lines_total'])],
 'cloud_logs_active':'loki.write ' in config or 'otelcol.exporter.otlp' in config,
 'cloud_traces_active':'otelcol.exporter.otlp' in config,'fleet_active':'remotecfg {' in config}
(OUT/'alloy-live.json').write_text(json.dumps(report,indent=2)+'\n')
for p in OUT.glob('*.json'):
 if p.stat().st_uid==0:os.chown(p,1000,1000)

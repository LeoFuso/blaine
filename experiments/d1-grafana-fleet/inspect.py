#!/usr/bin/env python3
"""Credential-safe read-only Fleet metadata inventory; not an agent capability."""
import base64,hashlib,json,runpy,sys,urllib.error,urllib.request
from pathlib import Path
root=Path(__file__).resolve().parents[2]
helper=runpy.run_path(str(root/'infra/grafana-cloud.py'))
v=helper['fleet_from_bws']()
headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((v['GRAFANA_CLOUD_FM_INSTANCE_ID']+':'+v['GRAFANA_CLOUD_FM_API_KEY']).encode()).decode()}
report={'fleet_api_authentication':'INCOMPLETE','collector_enrollment':'NOT_ACTIVATED','remote_assignment':'NOT_EXERCISED','telemetry':{'metrics':'INACTIVE_UNVALIDATED','logs':'INACTIVE_UNVALIDATED','traces':'INACTIVE_UNVALIDATED'}}
for kind,endpoint in [('collectors','collector.v1.CollectorService/ListCollectors'),('pipelines','pipeline.v1.PipelineService/ListPipelines')]:
 req=urllib.request.Request(v['GRAFANA_CLOUD_FM_URL']+'/'+endpoint,data=b'{}',headers=headers)
 try:
  with urllib.request.urlopen(req,timeout=20) as response:data=json.load(response)
  report[kind+'_http_status']=200
  report[kind]=[]
  for row in data.get(kind,[]):
   selected={k:row[k] for k in ['id','name','enabled','matchers','configType'] if k in row}
   if 'contents' in row:selected['contents_sha256']=hashlib.sha256(row['contents'].encode()).hexdigest()
   report[kind].append(selected)
 except urllib.error.HTTPError as error:report[kind+'_http_status']=error.code
report['fleet_api_authentication']='PASS' if report.get('collectors_http_status')==report.get('pipelines_http_status')==200 else 'STOP'
Path(sys.argv[1]).write_text(json.dumps(report,indent=2)+'\n')
print('Sanitized Fleet API metadata recorded; no remote mutation or config contents emitted')

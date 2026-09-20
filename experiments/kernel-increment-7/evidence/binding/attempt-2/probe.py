import hashlib,json,os,re,subprocess,threading,time,urllib.request,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path('/tmp/blaine-goose-binding-v2')
config=Path('/home/leofuso/.config/goose/config.yaml')
before=hashlib.sha256(config.read_bytes()).hexdigest()
records=[]
class Proxy(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_POST(self):
  url=urllib.parse.urlsplit(self.path)
  if url.scheme!='http' or url.hostname!='127.0.0.1' or url.port!=8000:
   self.send_error(403,'Only authorized local inference endpoint is permitted');return
  body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  record={'url':self.path,'request':json.loads(body),'authorization':'invocation-local non-secret EMPTY placeholder'}
  records.append(record)
  request=urllib.request.Request(self.path,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer EMPTY'})
  try:
   with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=60) as r:
    raw=r.read(); status=r.status; content_type=r.headers.get('Content-Type','application/json')
   frames=[]
   if 'event-stream' in content_type:
    for line in raw.decode().splitlines():
     if line.startswith('data: ') and line[6:]!='[DONE]': frames.append(json.loads(line[6:]))
   else: frames=[json.loads(raw)]
   record['response_models']=sorted({f['model'] for f in frames if 'model' in f})
   record['response_ids']=sorted({f['id'] for f in frames if 'id' in f})
   record['usage']=[f['usage'] for f in frames if f.get('usage')]
   texts=[]
   for frame in frames:
    for choice in frame.get('choices',[]):
     content=(choice.get('delta') or choice.get('message') or {}).get('content')
     if content: texts.append(content)
   record['response_content']=re.sub(r'<think>.*?</think>','', ''.join(texts),flags=re.S)
   record['status']=status
   self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
  except Exception as e:
   record['error']=type(e).__name__+': '+str(e);self.send_error(502,'Local binding failure')
server=ThreadingHTTPServer(('127.0.0.1',0),Proxy)
threading.Thread(target=server.serve_forever,daemon=True).start()
proxy='http://127.0.0.1:'+str(server.server_port)
settings={'GOOSE_PATH_ROOT':str(ROOT/'goose'),'GOOSE_DISABLE_KEYRING':'true','GOOSE_TELEMETRY_ENABLED':'false',
 'OPENAI_HOST':'http://127.0.0.1:8000','OPENAI_API_KEY':'EMPTY','HTTP_PROXY':proxy,'HTTPS_PROXY':proxy,'ALL_PROXY':proxy,'NO_PROXY':'',
 'http_proxy':proxy,'https_proxy':proxy,'all_proxy':proxy,'no_proxy':''}
env={k:v for k,v in os.environ.items() if k in ('PATH','HOME','USER','LANG','TMPDIR')};env.update(settings)
command=['/home/leofuso/.local/bin/goose','run','--no-profile','--no-session','--provider','openai','--model','Qwen/Qwen3.5-9B','--max-turns','1','--quiet','--text','Return exactly BINDING_OK. Do not call tools. Do not explain.']
report={'command':command,'cwd':str(ROOT),'environment_overrides':settings,'global_config_sha256_before':before,'evidence_scope':'binding only; no repository or Task changes'}
try:
 result=subprocess.run(command,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=90)
 report['exit_code']=result.returncode
 report['stdout_has_marker']=b'BINDING_OK' in result.stdout
 # Do not persist harness logs or hidden reasoning; wire evidence keeps only public content/model metadata.
 report['stdout_bytes']=len(result.stdout);report['stderr_bytes']=len(result.stderr)
 report['stderr_safe']=result.stderr.decode(errors='replace')[:1500]
except subprocess.TimeoutExpired:
 report['error']='Goose binding exceeded 90 seconds'
finally:
 deadline=time.monotonic()+20
 while any('status' not in r and 'error' not in r for r in records) and time.monotonic()<deadline:
  time.sleep(.1)
 server.shutdown()
 report['global_config_sha256_after']=hashlib.sha256(config.read_bytes()).hexdigest()
 report['requests']=records
 report['status']='PASS' if report.get('exit_code')==0 and records and all(r.get('status')==200 and r.get('response_models')==['Qwen/Qwen3.5-9B'] and r['request'].get('model')=='Qwen/Qwen3.5-9B' for r in records) and report.get('stdout_has_marker') and before==report['global_config_sha256_after'] else 'FAIL'
 (ROOT/'binding.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','command','exit_code','stderr_safe'] if k in report}))
 print('requests',len(records));print('evidence',ROOT/'binding.json')

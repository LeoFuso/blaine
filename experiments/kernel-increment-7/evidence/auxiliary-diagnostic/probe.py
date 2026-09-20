import hashlib,json,os,re,subprocess,threading,time,urllib.request,urllib.parse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
ROOT=Path('/tmp/blaine-goose-binding-v3')
config=Path('/home/leofuso/.config/goose/config.yaml')
before=hashlib.sha256(config.read_bytes()).hexdigest()
records=[]
class Proxy(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def do_POST(self):
  url=urllib.parse.urlsplit(self.path)
  if url.scheme!='http' or url.hostname!='127.0.0.1' or url.port!=8000 or url.path!='/v1/chat/completions':
   self.send_error(403,'Only authorized local inference endpoint is permitted');return
  body=self.rfile.read(int(self.headers.get('Content-Length','0')))
  record={'url':self.path,'request':json.loads(body),'purpose':'auxiliary_title' if b'Generate a short title' in body else 'main_worker','authorization':'invocation-local non-secret EMPTY placeholder'}
  records.append(record)
  if record['request'].get('model')!='Qwen/Qwen3.5-9B':
   record['blocked']='unauthorized model';self.send_error(403);return
  request=urllib.request.Request(self.path,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer EMPTY'})
  try:
   with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=30) as r:
    record['status']=r.status
    content_type=r.headers.get('Content-Type','application/json')
    self.send_response(r.status);self.send_header('Content-Type',content_type);self.end_headers()
    record['response_models']=[];record['response_ids']=[];record['usage']=[]
    frames=[];texts=[];record['stream_complete']=False
    if 'event-stream' in content_type:
     for line in r:
      if line.startswith(b'data: '):
       if line.strip()==b'data: [DONE]':record['stream_complete']=True
       else:
        frame=json.loads(line[6:]);frames.append(frame)
        if frame.get('model') and frame['model'] not in record['response_models']:record['response_models'].append(frame['model'])
        if frame.get('id') and frame['id'] not in record['response_ids']:record['response_ids'].append(frame['id'])
        if frame.get('usage'):record['usage'].append(frame['usage'])
        for choice in frame.get('choices',[]):
         content=(choice.get('delta') or choice.get('message') or {}).get('content')
         if content:texts.append(content)
      try:self.wfile.write(line);self.wfile.flush()
      except (BrokenPipeError,ConnectionResetError):record['client_disconnected']=True;break
    else:
     raw=r.read();frame=json.loads(raw);record['response_models']=[frame.get('model')]
     self.wfile.write(raw);record['stream_complete']=True
    record['response_content']=re.sub(r'<think>.*?</think>','', ''.join(texts),flags=re.S)
    record['capture_finished']=True
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
 deadline=time.monotonic()+5
 while any('capture_finished' not in r and 'error' not in r for r in records) and time.monotonic()<deadline:
  time.sleep(.1)
 server.shutdown()
 report['global_config_sha256_after']=hashlib.sha256(config.read_bytes()).hexdigest()
 report['requests']=records
 report['status']='PASS' if report.get('exit_code')==0 and records and all(r['url']=='http://127.0.0.1:8000/v1/chat/completions' and r['request'].get('model')=='Qwen/Qwen3.5-9B' and not r.get('blocked') for r in records) and any(r.get('purpose')=='main_worker' and r.get('response_models')==['Qwen/Qwen3.5-9B'] and r.get('status')==200 for r in records) and report.get('stdout_has_marker') and before==report['global_config_sha256_after'] else 'FAIL'
 (ROOT/'binding.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','command','exit_code','stderr_safe'] if k in report}))
 print('requests',len(records));print('evidence',ROOT/'binding.json')

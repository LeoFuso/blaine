"""Experiment-only streaming accountant; blocks every other endpoint/model/tool request."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time
import urllib.request
from urllib.parse import urlsplit
from runtime.kernel.model import NoRedirect


def start_capture(root, audit):
    class Proxy(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def do_CONNECT(self):
            audit('network.jsonl',{'event':'blocked','target':self.path})
            self.send_error(403)
        def do_POST(self):
            target=urlsplit(self.path)
            body=self.rfile.read(int(self.headers.get('Content-Length','0')))
            request=json.loads(body)
            record={'url':self.path,'request':request,
                    'purpose':'auxiliary_title' if b'Generate a short title' in body else 'main_worker'}
            if (target.scheme!='http' or target.hostname!='127.0.0.1' or target.port!=8000 or
                    target.path!='/v1/chat/completions' or request.get('model')!='Qwen/Qwen3.5-9B' or request.get('tools')):
                audit('network.jsonl',{'event':'blocked',**record});self.send_error(403);return
            audit('network.jsonl',{'event':'request',**record})
            if record['purpose']=='main_worker' and not (root/'first-main-seen').exists():
                (root/'first-main-seen').write_text('test-only interruption barrier before forwarding')
                audit('network.jsonl',{'event':'interruption_barrier','purpose':'main_worker'})
                while not (root/'release-first').exists(): time.sleep(.05)
                self.send_error(503);return
            req=urllib.request.Request(self.path,data=body,headers={'Content-Type':'application/json','Authorization':'Bearer EMPTY'})
            try:
                opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
                with opener.open(req,timeout=45) as response:
                    self.send_response(response.status);self.send_header('Content-Type',response.headers.get('Content-Type'));self.end_headers()
                    models=set(); complete=False; usage=None
                    for line in response:
                        if line.startswith(b'data: ') and line.strip()!=b'data: [DONE]':
                            frame=json.loads(line[6:]); model=frame.get('model')
                            if model and model not in models:
                                models.add(model);audit('network.jsonl',{'event':'response_model','purpose':record['purpose'],'model':model,'status':response.status})
                            if frame.get('usage'): usage=frame['usage']
                        if line.strip()==b'data: [DONE]':complete=True
                        try:self.wfile.write(line);self.wfile.flush()
                        except (BrokenPipeError,ConnectionResetError):break
                    audit('network.jsonl',{'event':'response_end','purpose':record['purpose'],'stream_complete':complete,'usage':usage})
            except Exception as error:
                audit('network.jsonl',{'event':'transport_error','purpose':record['purpose'],'error':type(error).__name__})
    server=ThreadingHTTPServer(('127.0.0.1',39111),Proxy)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

#!/usr/bin/env python3
"""Bounded local acceptance. Retains public output and measurements, not reasoning."""
import argparse
import concurrent.futures
import json
import math
from pathlib import Path
import subprocess
import time
import urllib.request

MODEL = 'nvidia/Qwen3.8-27B-NVFP4'


def request(port, path, body=None, timeout=600):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}',
        data=None if body is None else json.dumps(body).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else {'http_status': r.status}


def chat(prompt, **kwargs):
    body = dict(model=MODEL, messages=[{'role':'user','content':prompt}],
                max_tokens=512, temperature=0,
                chat_template_kwargs={'enable_thinking':False})
    body.update(kwargs)
    start=time.monotonic(); r=request(8000,'/v1/chat/completions',body)
    m=r['choices'][0]['message']
    return {'seconds':round(time.monotonic()-start,3),'usage':r.get('usage'),
            'content':m.get('content'),'tool_calls':m.get('tool_calls'),
            'reasoning_present':bool(m.get('reasoning') or m.get('reasoning_content')),
            'finish_reason':r['choices'][0]['finish_reason']}


def embeddings():
    start=time.monotonic()
    r=request(8001,'/v1/embeddings',{'model':'BAAI/bge-m3','input':[
        'Blaine retains durable Tasks in Restate.', 'MIRIX stores semantic memory.',
        'A synthetic reboot marker is not Task authority.']})
    assert len(r['data']) == 3
    for row in r['data']:
        assert len(row['embedding']) == 1024 and all(math.isfinite(x) for x in row['embedding'])
    return {'status':'PASS','vectors':3,'dimensions':1024,'seconds':round(time.monotonic()-start,3)}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    a.output.parent.mkdir(parents=True, exist_ok=True)
    out={}
    def save(): a.output.write_text(json.dumps(out,indent=2)+'\n')
    for port in [8000,8001]:
        out[str(port)]={'health':request(port,'/health'),'models':request(port,'/v1/models')}
    save()
    out['ordinary']=chat('Return exactly BLAINE_READY.');save()
    assert out['ordinary']['content'].strip()=='BLAINE_READY'
    out['reasoning']=chat('A box has 5 red and 3 blue balls. Two are drawn without replacement. What is the probability both are blue? Give the reduced fraction.',
                          chat_template_kwargs={'enable_thinking':True},max_tokens=2048);save()
    assert any(form in out['reasoning']['content'] for form in ['3/28', r'\frac{3}{28}'])
    out['structured']=chat('Return status ready and count 3.',response_format={'type':'json_schema','json_schema':{
        'name':'readiness','strict':True,'schema':{'type':'object','properties':{'status':{'const':'ready'},'count':{'const':3}},
        'required':['status','count'],'additionalProperties':False}}});save()
    assert json.loads(out['structured']['content']) == {'status':'ready','count':3}
    out['tools']=chat('Call inspect_task to inspect Task d1_acceptance. Do not invent its state.',
        tools=[{'type':'function','function':{'name':'inspect_task','description':'Inspect a durable Task',
            'parameters':{'type':'object','properties':{'task_id':{'type':'string'}},'required':['task_id']}}}],
        tool_choice='auto');save()
    call=out['tools']['tool_calls'][0]['function']
    assert call['name']=='inspect_task' and json.loads(call['arguments'])['task_id']=='d1_acceptance'
    with concurrent.futures.ThreadPoolExecutor() as pool:
        f=pool.submit(embeddings);out['simultaneous_generation']=chat('Return exactly COEXIST_READY.')
        out['embeddings']=f.result()
    assert out['simultaneous_generation']['content'].strip() == 'COEXIST_READY'
    out['vram']=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader'],text=True).strip()
    out['swap']=Path('/proc/swaps').read_text();save()
    out['status']='PASS';save()


if __name__=='__main__':main()

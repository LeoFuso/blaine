#!/usr/bin/env python3
"""Explicit synthetic memory acceptance; repeated runs retrieve the same fixture."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request
from urllib.parse import urlencode
import uuid

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
fixture = out / 'mirix-fixture.json'
if fixture.exists():
    f = json.loads(fixture.read_text())
else:
    nonce = uuid.uuid4().hex[:12]
    f = {'client_id':'client-df3da0d9','user_id':'probe-leofuso',
         'project':'D1Persistence_' + nonce, 'marker':'D1_AMBER_' + nonce.upper(),
         'tags':{'experiment':'d1-service-adoption','fixture':nonce}}
    fixture.write_text(json.dumps(f,indent=2)+'\n')

def call(path, body=None):
    req = urllib.request.Request('http://127.0.0.1:8531' + path,
          data=json.dumps(body).encode() if body is not None else None,
          headers={'x-client-id':f['client_id'],'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=240) as r:
        return json.load(r)

def search():
    query = {'user_id':f['user_id'],'query':f['project']+' release marker',
             'memory_type':'semantic','search_field':'details','search_method':'embedding',
             'limit':5,'filter_tags':json.dumps(f['tags']),'similarity_threshold':0.5}
    response = call('/memory/search?'+urlencode(query))
    rows = [r for r in response.get('results',[]) if f['marker'] in json.dumps(r)]
    assert rows, 'Synthetic fact not retrieved'
    return rows

if not f.get('memory_ids') and (out/'mirix-ingestion.json').exists():
    rows=search()
    f['memory_ids']=[r['id'] for r in rows]
    fixture.write_text(json.dumps(f,indent=2)+'\n')
    (out/'mirix-retrieved-before.json').write_text(json.dumps(rows,indent=2)+'\n')

if not f.get('memory_ids'):
    agents = call('/agents?limit=10')
    assert len(agents)==1
    assert agents[0]['llm_config']['model']=='nvidia/Qwen3.8-27B-NVFP4'
    body={'meta_agent_id':agents[0]['id'],'user_id':f['user_id'],
          'messages':[{'role':'user','content':f"Explicit synthetic semantic-memory fixture for Blaine D1 persistence. {f['project']} is the name of a new synthetic internal project for checking durable semantic memory across service restarts. Its release marker is exactly {f['marker']}. This is new project knowledge. Insert one new semantic memory item named {f['project']}, summary 'Synthetic internal persistence project', details containing its exact release marker, source 'operator-authorized D1 fixture', and tree path ['experiments', 'd1']. Do not merely check for an existing item: this project is new. This is disposable experiment data, not identity, policy or Task lifecycle state."}],
          'filter_tags':f['tags'],'use_cache':False,'verbose':True}
    receipt=call('/memory/add_sync',body)
    (out/'mirix-ingestion.json').write_text(json.dumps(receipt,indent=2)+'\n')
    assert receipt.get('success') is True, 'MIRIX ingestion failed; see receipt'
    rows=search()
    (out/'mirix-retrieved-before.json').write_text(json.dumps(rows,indent=2)+'\n')
    f['memory_ids']=[r['id'] for r in rows]
    fixture.write_text(json.dumps(f,indent=2)+'\n')
else:
    rows=search()
    assert sorted(r['id'] for r in rows)==sorted(f['memory_ids'])
print(json.dumps({'retrieved_ids':[r['id'] for r in rows],'marker':f['marker']}),flush=True)
if '--restart' in sys.argv:
    subprocess.run(['systemctl','--user','restart','blaine-mirix.service'],check=True,timeout=180)
    after=search()
    assert sorted(r['id'] for r in after)==sorted(f['memory_ids'])
    # Retrieval score may vary; exact semantic content and identity must not.
    keys=['id','name','summary','details','source']
    normalized=lambda items: sorted([{k:r.get(k) for k in keys} for r in items],key=lambda r:r['id'])
    assert normalized(rows)==normalized(after)
    (out/'mirix-retrieved-after.json').write_text(json.dumps(after,indent=2)+'\n')
    (out/'mirix-restart.json').write_text(json.dumps({'status':'PASS','memory_ids':f['memory_ids'],
        'content_sha256':hashlib.sha256(json.dumps(normalized(after),sort_keys=True).encode()).hexdigest(),
        'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n')
    print('MIRIX same identity/content after controlled restart: PASS',flush=True)

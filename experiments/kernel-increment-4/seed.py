"""Explicit experiment-only ingestion. Never called by the Cognitive Loop."""
import datetime
import json
import os
from pathlib import Path
import sys
import urllib.request
from urllib.parse import urlencode

OUT = Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8531'
CLIENT = 'client-df3da0d9'
USER = 'probe-leofuso'
TAG = 'kernel-increment-4-v1'


def save(name, value):
    (OUT / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')


def call(path, body=None):
    request = urllib.request.Request(BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'x-client-id': CLIENT, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


agents = call('/agents?limit=10')
assert len(agents) == 1
agent = agents[0]
llm, emb = agent['llm_config'], agent['embedding_config']
assert llm['model'] == 'Qwen/Qwen3.5-9B' and llm['model_endpoint'] == 'http://127.0.0.1:8000/v1'
assert emb['embedding_model'] == 'BAAI/bge-m3' and emb['embedding_endpoint'] == 'http://127.0.0.1:8001/v1'
save('binding', {'client_id': CLIENT, 'user_id': USER, 'agent_id': agent['id'],
    'llm_config': {k: llm[k] for k in ('model', 'model_endpoint', 'model_endpoint_type')},
    'embedding_config': {k: emb[k] for k in ('embedding_model','embedding_endpoint','embedding_endpoint_type','embedding_dim')},
    'pid': os.getpid(), 'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()})

fixtures = {
    'recall': 'Explicit disposable semantic-memory fixture for Blaine Increment 4. For project Aurelia, the release marker is exactly VIOLET_7429. Store this fact in semantic memory with the exact marker intact. This is experiment data, not a change to Blaine identity, policy, or Task state.',
    'conflict': 'Explicit disposable stale semantic-memory fixture for Blaine Increment 4. The old project Borealis release marker was exactly OLD_RED_1938. Store this historical fact in semantic memory. A later authoritative Task specification may override it. This is experiment data, not Task state or policy.',
}
for case, content in fixtures.items():
    tags = {'experiment': TAG, 'fixture': case}
    body = {'meta_agent_id': agent['id'], 'user_id': USER,
        'messages': [{'role': 'user', 'content': content}], 'filter_tags': tags,
        'use_cache': False, 'verbose': False}
    save(case + '-seed-request', {'method': 'POST', 'endpoint': BASE + '/memory/add_sync', 'body': body})
    receipt = call('/memory/add_sync', body)
    save(case + '-seed-receipt', receipt)
    assert receipt.get('success') is True, receipt
    query = {'user_id': USER, 'query': 'project ' + ('Aurelia' if case == 'recall' else 'Borealis') + ' release marker',
        'memory_type': 'semantic', 'search_field': 'details', 'search_method': 'embedding',
        'limit': 2, 'filter_tags': json.dumps(tags), 'similarity_threshold': 0.5}
    result = call('/memory/search?' + urlencode(query))
    save(case + '-seed-readback', {'query': query, 'response': result})
    marker = 'VIOLET_7429' if case == 'recall' else 'OLD_RED_1938'
    assert any(marker in json.dumps(x) for x in result.get('results', [])), result
    print('Seed verified:', case, flush=True)
save('seed-complete', {'pid': os.getpid(), 'completed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'explicit_writes': 2, 'automatic_ingestion': False})

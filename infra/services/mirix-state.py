#!/usr/bin/env python3
"""Read-only MIRIX identity/config/hash inventory; never emits memory or secrets."""
import configparser
import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
from sqlalchemy import create_engine, text

c = configparser.ConfigParser()
source = Path.home()/'.mirix/config'
c.read(source)
uri = c['recall_storage']['uri']
assert uri == c['archival_storage']['uri']
address = urlsplit(uri)
out = {'observed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'config_path':str(source),'config_mode':oct(source.stat().st_mode & 0o777),
       'database':{'host':address.hostname,'port':address.port,'database':address.path,'user':address.username},
       'mirix_revision':subprocess.check_output(['git','-C',str(Path.home()/'workspace/mirix'),'rev-parse','HEAD'],text=True).strip(),
       'python':sys.version.split()[0], 'agents':[], 'semantic_memories':[]}
with create_engine(uri).connect() as db:
    out['postgresql_version'] = db.execute(text('select version()')).scalar()
    for row in db.execute(text('select id,client_id,user_id,name,summary,details,source from semantic_memory where not is_deleted order by id')):
        d = dict(row._mapping)
        out['semantic_memories'].append({'id':d['id'],'client_id':d['client_id'],'user_id':d['user_id'],
            'content_sha256':hashlib.sha256(json.dumps({k:d[k] for k in ['name','summary','details','source']},sort_keys=True).encode()).hexdigest()})
    for row in db.execute(text('select id,name,llm_config,embedding_config from agents where not is_deleted order by id')):
        d = dict(row._mapping)
        for field in ['llm_config','embedding_config']:
            d[field] = {k:v for k,v in d[field].items() if k in ['model','model_endpoint','model_endpoint_type','context_window','embedding_model','embedding_endpoint','embedding_endpoint_type','embedding_dim','embedding_chunk_size']}
        out['agents'].append(d)
Path(sys.argv[1]).write_text(json.dumps(out,indent=2)+'\n')
print('Recorded MIRIX identities and content hashes:',len(out['semantic_memories']),'memories')

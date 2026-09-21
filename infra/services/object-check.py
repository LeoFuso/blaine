#!/usr/bin/env python3
"""Create once/read thereafter an explicitly synthetic D1.G object; no deletion."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import uuid

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
Services=runpy.run_path(str(Path(__file__).resolve().parents[1]/'rootless/accept-services.py'))['Services']
client=Services(Path.home()/'.config/blaine/secrets').s3('blaine')
fixture=out/'object-fixture.json'
if fixture.exists():f=json.loads(fixture.read_text())
else:
    f={'bucket':'blaine-artifacts','key':'d1-service-adoption/'+uuid.uuid4().hex+'.txt',
       'content':'Synthetic Blaine D1.G durable object. Preserve across the separately authorized reboot.\n'}
    f['sha256']=hashlib.sha256(f['content'].encode()).hexdigest()
    client.put_object(Bucket=f['bucket'],Key=f['key'],Body=f['content'].encode(),ContentType='text/plain')
    fixture.write_text(json.dumps(f,indent=2)+'\n')
body=client.get_object(Bucket=f['bucket'],Key=f['key'])['Body'].read()
assert hashlib.sha256(body).hexdigest()==f['sha256'] and body.decode()==f['content']
print('Object identity/content: PASS',f['key'])

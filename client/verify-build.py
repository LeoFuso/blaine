#!/usr/bin/env python3
"""Verify release payloads, repeat builds and native metadata; write one manifest."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

out = Path(sys.argv[1]).resolve()
names = ['blaine-darwin-amd64', 'blaine-darwin-arm64', 'blaine-linux-amd64', 'blaine-linux-arm64']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert {p.name for p in (out/'bin').iterdir()} <= set(names) | {'checksums.txt'}
artifacts = []
for name in names:
    path = out/'bin'/name
    digest = sha(path)
    assert digest == sha(out/'rebuild'/name), f'non-reproducible build: {name}'
    artifacts.append({'name':name, 'sha256':digest, 'bytes':path.stat().st_size,
                      'format':subprocess.check_output(['file','-b',str(path)],text=True).strip()})
metadata = json.loads(subprocess.check_output([str(out/'bin'/'blaine-linux-amd64'),'version','--json']))
assert metadata['client_version'] == os.environ['BLAINE_VERSION']
assert metadata['build_commit'] == os.environ['BLAINE_COMMIT']
assert metadata['protocol_version'] == 2
assert metadata['go_version'] == 'go' + Path('client/.go-version').read_text().strip()
assert 'INTERP' not in subprocess.check_output(['readelf','-l',str(out/'bin'/'blaine-linux-amd64')],text=True)
(out/'bin'/'checksums.txt').write_text(''.join(f"{a['sha256']}  {a['name']}\n" for a in artifacts))
(out/'validation'/'build-info.json').write_text(json.dumps({'metadata':metadata,'artifacts':artifacts,
    'repeat_build_identical':True,'linux_amd64_dynamic_interpreter':False,
    'runtime_scope':'Linux amd64 offline fixtures only; cross-platform builds do not establish live E0.D acceptance'},indent=2)+'\n')
print('PASS: four repeat builds, exact version/protocol/commit, static Linux binary, checksums.txt')

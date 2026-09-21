#!/usr/bin/env python3
"""Inventory only service identities/ownership, never process environments."""
import json
from pathlib import Path
import subprocess
import sys

rows=[]
for process in Path('/proc').iterdir():
    if not process.name.isdigit():continue
    try:
        cmd=(process/'cmdline').read_bytes().split(b'\0')
        text=b' '.join(cmd)
        labels=[]
        if any(b'vllm' in x for x in cmd[:2]) or b'VLLM::' in text:labels.append('inference')
        if cmd and Path(cmd[0].decode(errors='replace')).name=='restate-server':labels.append('restate')
        if b'scripts/start_server.py' in cmd:labels.append('mirix')
        if b'runtime.personal_runtime' in cmd:labels.append('blaine')
        if not labels:continue
        fields=(process/'stat').read_text().rsplit(')',1)[1].split()
        rows.append({'pid':int(process.name),'roles':labels,'ppid':int(fields[1]),'tty':int(fields[4]),
                     'cgroup':(process/'cgroup').read_text().strip()})
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
Path(sys.argv[1]).write_text(json.dumps({'processes':rows},indent=2)+'\n')
assert all(r['tty']==0 for r in rows), 'Terminal-owned service found'
assert all('blaine-' in r['cgroup'] and '.service' in r['cgroup'] for r in rows), 'Unmanaged duplicate found'
print('PASS: all observed runtime processes belong to Blaine user services without terminals')

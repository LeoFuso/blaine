#!/usr/bin/env python3
"""Bounded startup readiness; no Task state or background supervisor."""
import argparse
import json
import subprocess
import time
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--timeout', type=int, default=180)
p.add_argument('--unit', help='Fail immediately if this service main process exits')
p.add_argument('urls', nargs='+')
a = p.parse_args()
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + a.timeout
pending = set(a.urls)
while pending and time.monotonic() < deadline:
    if a.unit:
        pid = subprocess.check_output(['systemctl','--user','show',a.unit,'-p','MainPID','--value'],text=True).strip()
        if not pid.isdigit() or int(pid) == 0:
            raise SystemExit('Service process exited before readiness: ' + a.unit)
    for url in list(pending):
        try:
            with opener.open(url, timeout=3) as r:
                if r.status == 200:
                    r.read(65536)
                    pending.remove(url)
        except (OSError, ValueError):
            pass
    if pending:
        time.sleep(1)
if pending:
    raise SystemExit('Readiness deadline exceeded: ' + ', '.join(sorted(pending)))
print('Readiness checks passed')

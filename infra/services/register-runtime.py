#!/usr/bin/env python3
"""Register the actual deployed kernel after bounded readiness; no Task creation."""
import json
import time
import urllib.request

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + 120
while True:
    try:
        req = urllib.request.Request('http://127.0.0.1:49070/deployments',
            data=json.dumps({'uri': 'http://127.0.0.1:49080'}).encode(),
            headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=5) as response:
            value = json.load(response)
        print('Blaine deployment registration ready')
        break
    except OSError:
        if time.monotonic() >= deadline:
            raise SystemExit('Blaine deployment registration readiness failed') from None
        time.sleep(1)

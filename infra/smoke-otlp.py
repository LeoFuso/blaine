#!/usr/bin/env python3
"""Emit only synthetic metrics/logs/traces to Alloy's loopback OTLP receiver."""
import json
import secrets
import time
import urllib.request

n = str(time.time_ns())
trace_id = secrets.token_hex(16)
resource = {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'blaine-d1-synthetic'}}]}
scope = {'name': 'd1.acceptance'}
payloads = {
    'traces': {'resourceSpans': [{'resource': resource, 'scopeSpans': [{'scope': scope, 'spans': [{
        'traceId': trace_id, 'spanId': secrets.token_hex(8), 'name': 'd1-activation-smoke',
        'startTimeUnixNano': n, 'endTimeUnixNano': str(int(n) + 1000000), 'kind': 1}]}]}]},
    'metrics': {'resourceMetrics': [{'resource': resource, 'scopeMetrics': [{'scope': scope, 'metrics': [{
        'name': 'd1.synthetic.value', 'gauge': {'dataPoints': [{'timeUnixNano': n, 'asDouble': 1.0}]}}]}]}]},
    'logs': {'resourceLogs': [{'resource': resource, 'scopeLogs': [{'scope': scope, 'logRecords': [{
        'timeUnixNano': n, 'severityNumber': 9, 'body': {'stringValue': 'D1 synthetic activation smoke'}}]}]}]},
}
for signal, payload in payloads.items():
    req = urllib.request.Request('http://127.0.0.1:4318/v1/' + signal, data=json.dumps(payload).encode(),
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read())
        partial = result.get('partialSuccess', {})
        if any(partial.get(k, 0) not in (0, '0') for k in ['rejectedSpans', 'rejectedDataPoints', 'rejectedLogRecords']):
            raise SystemExit(f'{signal}: partially rejected')
        print(signal + ': accepted locally')
print('Synthetic trace ID: ' + trace_id)
print('Local acceptance alone does not prove Grafana Cloud delivery.')

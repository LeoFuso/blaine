#!/usr/bin/env python3
"""Summarize outbound attempts from strace logs of one sandboxed Letta state.

Reports every connect() destination grouped by address/port with its result,
DNS query names recovered from sendto/sendmsg payloads to port 53, execve'd
programs, and requests recorded by the in-sandbox LETTA_BASE_URL sink.
Loopback bridges (18000 vLLM, 18001 scripted model, own listener) are expected.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

CONNECT = re.compile(r'connect\(\d+, \{sa_family=(AF_INET6?|AF_UNIX)(?:, sin6?_port=htons\((\d+)\))?(?:, sin_addr=inet_addr\("([^"]+)"\)|, inet_pton\(AF_INET6, "([^"]+)"|, sun_path="([^"]+)")?.*?\) = (.*)$')
DNS_NAME = re.compile(r'((?:\\\d{1,3}|\\[a-z])[A-Za-z0-9-]{1,63})+')


def dns_names(line):
    # strace escapes the wire-format labels, e.g. \3api\5letta\3com
    names = []
    for match in re.finditer(r'"([^"]*)"', line):
        payload = match.group(1)
        labels = re.findall(r'\\(\d{1,3})([A-Za-z0-9-]+)', payload)
        if len(labels) >= 2:
            names.append('.'.join(label for _, label in labels))
    return names


def main():
    state = Path(sys.argv[1])
    connects, dns, execs = Counter(), Counter(), Counter()
    for log in sorted((state / 'logs').glob('strace-*.txt')):
        for line in log.read_text(errors='replace').splitlines():
            if 'connect(' in line:
                m = CONNECT.search(line)
                if m:
                    family, port, ip4, ip6, path, result = m.groups()
                    dest = path or f'{ip4 or ip6}:{port}'
                    connects[(family, dest, result.split(' ')[0] if result else '?')] += 1
            if ('sendto(' in line or 'sendmsg(' in line) and ('htons(53)' in line or '\\0\\1\\0\\0' in line):
                for name in dns_names(line):
                    dns[name] += 1
            if 'execve(' in line and '= 0' in line:
                m = re.search(r'execve\("([^"]+)"', line)
                if m:
                    execs[m.group(1)] += 1
    sink = state / 'logs/egress-sink.jsonl'
    requests = [json.loads(l) for l in sink.read_text().splitlines()] if sink.exists() else []
    print(json.dumps({
        'state': state.name,
        'connects': [{'family': f, 'dest': d, 'result': r, 'count': c} for (f, d, r), c in sorted(connects.items())],
        'dns_queries': dict(dns),
        'execve': dict(execs),
        'sink_requests': Counter(f"{r['method']} {r['path']}" for r in requests),
        'sink_bytes': sum(r['body_bytes'] for r in requests),
    }, indent=1, default=dict))


if __name__ == '__main__':
    main()

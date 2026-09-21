#!/usr/bin/env python3
"""Validate a running candidate or migrated stack; no daemon/service mutations."""
import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'experiments/d1-rootless-docker-adoption/evidence'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


services = module('accept_services', 'accept-services.py')
preflight = module('preflight', 'preflight.py')


def validate(candidate, seed, baseline, output):
    report = {'status': 'INCOMPLETE', 'scope': 'candidate' if candidate else 'migrated rootless stack', 'checks': {}}
    try:
        preflight.daemon()
        project = 'blaine-rootless-full-candidate' if candidate else 'blaine-infra-rootless'
        cids = subprocess.check_output(['docker', '--context', 'rootless', 'ps', '-q', '--filter', 'label=com.docker.compose.project=' + project], text=True).split()
        assert len(cids) == 4
        for cid in cids:
            state = subprocess.check_output(['docker', '--context', 'rootless', 'inspect', '--format', '{{.State.Health.Status}}', cid], text=True).strip()
            assert state == 'healthy'
        report['checks']['four_rootless_containers_healthy'] = 'PASS'
        secret_dir = (Path.home() / '.local/share/blaine/rootless-full-candidate-20260921/secrets') if candidate else Path.home() / '.config/blaine/secrets'
        preflight.private(secret_dir, directory=True)
        for p in secret_dir.iterdir():
            preflight.private(p)
        client = services.Services(secret_dir, **({'s3_port': 18333, 'ch_port': 18123, 'web_port': 13000, 'worker_port': 13030} if candidate else {}))
        client.health()
        report['checks']['http_health'] = 'PASS'
        if seed:
            report['checks']['seed'] = client.seed()
        if baseline:
            report['checks']['retained_original_state'] = client.verify_snapshot(json.loads(baseline.read_text()))
        report['checks']['langfuse_roundtrip'] = client.roundtrip()
        report['snapshot'] = client.snapshot()
        trace = report['checks']['langfuse_roundtrip']
        report['snapshot']['retained_traces'] = [{'trace_id': trace['trace_id'], 'since': trace['since'], 'count': 1}]
        ports = [18333,18123,19000,13000,13030,16379] if candidate else [8333,8123,9000,3000,3030]
        for port in ports:
            lines = subprocess.check_output(['ss', '-H', '-lnt', f'sport = :{port}'], text=True).splitlines()
            assert lines and all(line.split()[3] == f'127.0.0.1:{port}' for line in lines)
        report['checks']['private_loopback_listeners'] = 'PASS'
        report['status'] = 'PASS'
    except Exception as exc:
        report['status'] = 'STOP'
        report['failure_type'] = type(exc).__name__
    report['observed_at'] = datetime.now(timezone.utc).isoformat()
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'snapshot'}, indent=2))
    return report['status'] == 'PASS'


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--candidate', action='store_true')
    parser.add_argument('--seed', action='store_true')
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.exit(0 if validate(args.candidate, args.seed, args.baseline, args.output) else 1)

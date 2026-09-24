"""Read-only deployed E0.C readiness; never a caller-controlled fixture bypass."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import urllib.parse
import urllib.request

from runtime.host_connection import BoundaryError, SERVICES, decode, readiness


def inspect(config, deployment, fetch=None):
    if fetch is None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise BoundaryError('readiness redirect denied')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

        def fetch(url, headers):
            with opener.open(urllib.request.Request(url, headers=headers), timeout=7) as response:
                if response.status != 200:
                    raise BoundaryError('readiness failed')
                body = response.read(65537)
                return decode(body) if body else None

    def memory():
        try:
            m = deployment['memory']
            if m['endpoint'].rstrip('/') != 'http://127.0.0.1:8531':
                return 'FAIL'
            query = urllib.parse.urlencode({
                'query': 'Blaine host connection readiness', 'memory_type': 'semantic',
                'search_field': 'details', 'search_method': 'embedding', 'limit': 1,
                'similarity_threshold': 0.99, 'include_core_memory': 'false',
                'user_id': m['user_id']})
            data = fetch(m['endpoint'].rstrip('/') + '/memory/search?' + query,
                         {'x-client-id': m['client_id']})
            return 'PASS' if (data.get('success') is True and data.get('search_method') == 'embedding'
                              and isinstance(data.get('results'), list) and len(data['results']) <= 1) else 'FAIL'
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return 'FAIL'

    # A bounded real retrieval proves the configured tenant/database/embedding
    # path. Its memory content is neither logged nor sent to the workstation.
    with ThreadPoolExecutor(max_workers=2) as pool:
        mem = pool.submit(memory)
        report = readiness(config, lambda url: fetch(url, {
            'Accept': 'application/vnd.restate.endpointmanifest.v3+json'} if url.endswith('/discover') else {}))
        report['mirix'] = mem.result()
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--deployment', required=True, type=Path)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        deployment = json.loads(args.deployment.read_text())
        if config['generation_model'] != deployment['cognition']['model']:
            raise ValueError('configured runtime model mismatch')
        report = inspect(config, deployment)
    except (OSError, ValueError, KeyError, TypeError):
        report = {name: 'FAIL' for name in SERVICES}
    print(json.dumps(report, sort_keys=True))
    return 0 if set(report.values()) == {'PASS'} else 2


if __name__ == '__main__':
    raise SystemExit(main())

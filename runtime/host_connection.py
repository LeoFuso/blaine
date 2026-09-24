#!/usr/bin/env python3
"""E0.C bounded host control boundary; no listener or Task lifecycle ownership.

Trusted peer binding is deliberately unavailable until the designated second
workstation proves the installed Tailscale SSH launcher. There is no environment,
JSON, argv, or fixture switch that bypasses that production gate.
"""
import json
from concurrent.futures import ThreadPoolExecutor
import re
import sys
import urllib.request

LIMIT = 65536
FEATURES = ['handshake-v1', 'acp-ndjson', 'no-workspace-effects']
SERVICES = ('runtime', 'restate', 'mirix', 'generation', 'embeddings')


class BoundaryError(ValueError):
    pass


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BoundaryError('duplicate JSON key')
        result[key] = value
    return result


def decode(data):
    if len(data) > LIMIT:
        raise BoundaryError('control input too large')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(BoundaryError('invalid number')))
    except (ValueError, UnicodeError, RecursionError):
        raise BoundaryError('malformed control JSON') from None


def trusted_peer():
    # SSH_CONNECTION is mutable by a remote command. whois(claimed_ip) only
    # identifies that claimed address; it does not authenticate the current caller.
    # The version-matched Linux non-PTY incubator execs su, losing its original
    # peer argv. Do not promote an unproved process/env correlation into identity.
    raise BoundaryError('PEER_UNVERIFIED: second-workstation trusted transport binding pending; no launch')


def handshake(request, config, peer, readiness):
    """Pure negotiation; peer/readiness come from host observations, never JSON."""
    if not isinstance(request, dict) or set(request) != {
        'schema_version', 'client_version', 'protocol', 'expected_server_id', 'client_id'
    }:
        raise BoundaryError('invalid handshake fields')
    protocol = request['protocol']
    if (type(request['schema_version']) is not int or request['schema_version'] != 1
            or not isinstance(protocol, dict) or set(protocol) != {'min', 'max'}
            or any(type(protocol[k]) is not int for k in ('min', 'max'))
            or not 1 <= protocol['min'] <= 1 <= protocol['max']):
        raise BoundaryError('INCOMPATIBLE: host supports Blaine protocol 1')
    for key in ('client_id', 'client_version'):
        if not isinstance(request[key], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', request[key]):
            raise BoundaryError('invalid client metadata')
    expected = request['expected_server_id']
    if not isinstance(expected, str) or expected not in ('', config['server_id']):
        raise BoundaryError('IDENTITY_MISMATCH: expected server differs')
    if (not isinstance(peer, dict) or set(peer) != {'device_id', 'principal_id', 'ssh_user', 'source'}
            or peer.get('source') != 'trusted-transport' or peer.get('ssh_user') != config['ssh_user']
            or any(not isinstance(peer.get(k), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', peer[k])
                   for k in ('device_id', 'principal_id'))):
        raise BoundaryError('PEER_UNVERIFIED: trusted device/principal/user required')
    return {'schema_version': 1, 'server_id': config['server_id'], 'server_version': '0.1.0-e0c',
            'protocol': {'min': 1, 'max': 1}, 'selected_protocol': 1, 'peer': peer,
            'registration_status': 'not-implemented', 'features': FEATURES,
            'readiness': {name: readiness.get(name, 'UNKNOWN') for name in SERVICES}}


def readiness(config, fetch=None):
    """Bounded read-only probes; no model calls, memory mutation or service starts.

    HTTP liveness alone cannot prove runtime routing or MIRIX dependencies. Those
    remain UNKNOWN until their semantic readiness predicate is live-validated.
    """
    if fetch is None:
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                raise BoundaryError('readiness redirect denied')
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

        def fetch(url):
            request = urllib.request.Request(url, headers={'Accept': 'application/vnd.restate.endpointmanifest.v3+json'} if url.endswith('/discover') else {})
            with opener.open(request, timeout=1) as response:
                body = response.read(LIMIT + 1)
                if response.status != 200:
                    raise BoundaryError('readiness failed')
                return decode(body) if body else None
    def probe(name):
        try:
            if name == 'runtime':
                manifest = fetch('http://127.0.0.1:49080/discover')
                service = next(s for s in manifest['services'] if s['name'] == 'CognitiveTaskV1')
                handlers = {h['name'] for h in service['handlers']}
                return 'PASS' if {'run', 'inspect', 'cancel'}.issubset(handlers) else 'FAIL'
            if name == 'restate':
                deployments = fetch('http://127.0.0.1:49070/deployments')['deployments']
                expected = config.get('deployment_id')
                return 'PASS' if expected and any(
                    d['id'] == expected and d['uri'].rstrip('/') == 'http://127.0.0.1:49080'
                    and any(s['name'] == 'CognitiveTaskV1' for s in d['services'])
                    for d in deployments) else 'UNKNOWN'
            if name == 'mirix':
                health = fetch('http://127.0.0.1:8531/health')
                # Installed MIRIX's /health is unconditional. Its response proves
                # liveness, not database/model readiness. Keep that gap visible.
                return 'UNKNOWN' if health.get('status') == 'healthy' else 'FAIL'
            port = 8000 if name == 'generation' else 8001
            fetch(f'http://127.0.0.1:{port}/health')
            models = fetch(f'http://127.0.0.1:{port}/v1/models')
            expected = config.get(name + '_model')
            return 'PASS' if expected and any(m.get('id') == expected for m in models['data']) else 'FAIL'
        except (OSError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
            return 'FAIL'
    with ThreadPoolExecutor(max_workers=5) as pool:
        return dict(zip(SERVICES, pool.map(probe, SERVICES)))



def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv not in (['handshake'], ['acp']):
        print('usage: blaine-host-connection handshake|acp', file=sys.stderr)
        return 64
    try:
        # Fail before consuming stdin or loading runtime code. No request can
        # nominate a peer, bypass identity or accidentally create a Task.
        trusted_peer()
    except BoundaryError as error:
        print(str(error), file=sys.stderr)
        return 2
    # A verified binding and installed deployment remain the live acceptance gate.
    # Do not ship an ACP launch path conditional only on caller-controlled state.
    return 2


if __name__ == '__main__':
    raise SystemExit(main())

import contextlib
import io
import os
import unittest
from unittest.mock import patch

from runtime.host_connection import BoundaryError, decode, handshake, main, readiness, trusted_peer


class HostConnectionTests(unittest.TestCase):
    def setUp(self):
        self.request = dict(schema_version=1, client_version='0.1.0-e0c', protocol=dict(min=1, max=1),
                            expected_server_id='server-1', client_id='client-1')
        self.config = dict(server_id='server-1', ssh_user='leofuso')
        self.peer = dict(device_id='device-1', principal_id='principal-1', ssh_user='leofuso', source='trusted-transport')

    def test_fixture_negotiation_and_unknown_readiness(self):
        response = handshake(self.request, self.config, self.peer, {})
        self.assertEqual(response['selected_protocol'], 1)
        self.assertEqual(set(response['readiness'].values()), {'UNKNOWN'})
        self.assertEqual(response['registration_status'], 'not-implemented')

    def test_identity_protocol_and_claim_rejections(self):
        for change in [dict(expected_server_id='wrong'), dict(protocol=dict(min=2, max=3)),
                       dict(schema_version=True), dict(peer=self.peer), dict(client_id='')]:
            with self.subTest(change=change), self.assertRaises(BoundaryError):
                handshake(self.request | change, self.config, self.peer, {})
        for change in [dict(source='SSH_CONNECTION'), dict(ssh_user='root'), dict(device_id='')]:
            with self.assertRaises(BoundaryError):
                handshake(self.request, self.config, self.peer | change, {})

    def test_production_cannot_accept_spoofed_environment(self):
        with patch.dict(os.environ, {'SSH_CONNECTION': '100.64.0.2 123 100.64.0.1 22',
                                     'BLAINE_PEER_ID': 'device-1', 'BLAINE_TRUSTED_PEER': 'true'}):
            with self.assertRaises(BoundaryError):
                trusted_peer()
            for operation in ('handshake', 'acp'):
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    self.assertEqual(main([operation]), 2)
                self.assertEqual(stdout.getvalue(), '')
                self.assertIn('PEER_UNVERIFIED', stderr.getvalue())

    def test_readiness_does_not_infer_runtime_health(self):
        calls = []
        def fetch(url):
            calls.append(url)
            if url.endswith('/discover'):
                return {'services':[{'name':'CognitiveTaskV1', 'handlers':[{'name':n} for n in ('run','inspect','cancel')]}]}
            if url.endswith('/deployments'):
                return {'deployments':[]}
            if ':8531/' in url:
                return {'status':'healthy'}
            return {'data': [{'id': 'fixture-model'}]}
        result = readiness(self.config | {'generation_model': 'fixture-model', 'embeddings_model': 'wrong'}, fetch)
        self.assertEqual(result['generation'], 'PASS')
        self.assertEqual(result['embeddings'], 'FAIL')
        self.assertEqual(result['runtime'], 'PASS')
        self.assertEqual(result['restate'], 'UNKNOWN')
        self.assertEqual(result['mirix'], 'UNKNOWN')
        self.assertEqual(len(calls), 7)
        self.assertTrue(all(url.startswith('http://127.0.0.1:') for url in calls))

    def test_malformed_input(self):
        for data in (b'{"a":1,"a":2}', b'{} {}', b'{"x":NaN}', b'x' * 65537, b'"\xff"'):
            with self.assertRaises(BoundaryError):
                decode(data)


if __name__ == '__main__':
    unittest.main()

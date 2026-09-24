"""The Personal Agent bridge is a thin, origin-restricted JSON transport."""
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError

from runtime import personal_http


class BridgeTransport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ['BLAINE_CONVERSATION_KEY_DIR'] = cls.tmp.name + '/keys'
        personal_http.services.data_dir = __import__('pathlib').Path(cls.tmp.name) / 'data'
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), personal_http.BridgeHandler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.server.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        os.environ.pop('BLAINE_CONVERSATION_KEY_DIR', None)
        cls.tmp.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        req = urllib.request.Request(self.base + path, data=body, method=method, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, dict(response.headers), response.read()
        except HTTPError as error:
            return error.code, dict(error.headers), error.read()

    def test_preflight_only_for_the_app_origins(self):
        status, headers, _ = self.request('/conversation/create', 'OPTIONS',
                                          headers={'Origin': 'http://localhost:1420'})
        self.assertEqual((status, headers['Access-Control-Allow-Origin']), (204, 'http://localhost:1420'))
        status, headers, _ = self.request('/conversation/create', 'OPTIONS', headers={'Origin': 'https://evil.example'})
        self.assertEqual(status, 403)
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_posts_must_be_json(self):
        body = json.dumps({'conversation_id': 'c1'}).encode()
        status, _, _ = self.request('/conversation/create', 'POST', body, {'Content-Type': 'text/plain'})
        self.assertEqual(status, 415)
        status, headers, data = self.request('/conversation/create', 'POST', body,
                                             {'Content-Type': 'application/json', 'Origin': 'tauri://localhost'})
        self.assertEqual((status, json.loads(data)['id']), (200, 'c1'))
        self.assertEqual(headers['Access-Control-Allow-Origin'], 'tauri://localhost')


if __name__ == '__main__':
    unittest.main()

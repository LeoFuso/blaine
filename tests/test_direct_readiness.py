import unittest
from runtime.direct_readiness import inspect


class DirectReadinessTests(unittest.TestCase):
    def test_liveness_does_not_substitute_for_memory_readiness(self):
        config = {'deployment_id': 'deployment', 'generation_model': 'model', 'embeddings_model': 'model'}
        deployment = {'memory': {'endpoint': 'http://127.0.0.1:8531', 'user_id': 'fixture-user', 'client_id': 'fixture-client'}}
        memory_result = {'success': True, 'results': [], 'search_method': 'embedding'}
        searches = []
        def fetch(url, headers):
            if '/memory/search?' in url:
                searches.append((url, headers))
                return memory_result
            if url.endswith('/discover'):
                return {'services': [{'name': 'CognitiveTaskV1', 'handlers': [{'name': n} for n in ('run', 'inspect', 'cancel')]}]}
            if url.endswith('/deployments'):
                return {'deployments': [{'id': 'deployment', 'uri': 'http://127.0.0.1:49080', 'services': [{'name': 'CognitiveTaskV1'}]}]}
            if ':8531' in url:
                return {'status': 'healthy'}
            return {'data': [{'id': 'model'}]}
        self.assertEqual(set(inspect(config, deployment, fetch).values()), {'PASS'})
        self.assertEqual(searches[0][1], {'x-client-id': 'fixture-client'})
        self.assertIn('limit=1', searches[0][0])
        for invalid in ({'status': 'healthy'}, {'success': False}, {'success': True, 'results': [], 'search_method': 'text'}):
            memory_result = invalid
            self.assertEqual(inspect(config, deployment, fetch)['mirix'], 'FAIL')
        deployment['memory']['endpoint'] = 'https://untrusted.example'
        self.assertEqual(inspect(config, deployment, fetch)['mirix'], 'FAIL')

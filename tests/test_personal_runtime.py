import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from runtime.personal_runtime import application, no_unnecessary_cognition


class DeploymentTests(unittest.TestCase):
    def test_default_remains_deterministic_and_operator_selects_local_adapters(self):
        with tempfile.TemporaryDirectory() as directory, patch('runtime.personal_runtime.create_workflow') as create, patch('runtime.personal_runtime.restate.app'):
            application(Path(directory))
            self.assertIs(create.call_args.args[1], no_unnecessary_cognition)
            self.assertIsNone(create.call_args.args[2].worker)
            deployment = {'cognition': {'model': 'local-fixture', 'endpoint': 'http://127.0.0.1:8000/v1'},
                'memory': {'client_id': 'fixture', 'endpoint': 'http://127.0.0.1:8531'},
                'goose': '/usr/bin/false'}
            application(Path(directory), deployment)
            self.assertEqual(create.call_args.args[1].model, 'local-fixture')
            self.assertEqual(create.call_args.args[2].worker.model, 'local-fixture')
            self.assertEqual(create.call_args.kwargs['providers'][0].client_id, 'fixture')
            deployment['cognition']['endpoint'] = 'https://external.example/v1'
            with self.assertRaises(ValueError):
                application(Path(directory), deployment)

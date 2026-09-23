"""Deterministic controls for explicit secret materialization.

Run: python3 -m unittest discover -s tests/platform -v

Bitwarden and the keyring are faked. Nothing here reads a real credential store,
and no test asserts on a secret value beyond proving it never leaks.
"""
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'blaine_secrets', Path(__file__).resolve().parents[2] / 'infra/secrets.py')
secrets = importlib.util.module_from_spec(spec)
spec.loader.exec_module(secrets)

VALUE = 'fixture-value-0123456789abcdef'
OTHER = 'undeclared-value-0123456789abcd'
TOKEN = 'fixture-bootstrap-token'


def declarations(root, **changes):
    document = {
        'version': 1,
        'source': {'provider': 'bitwarden-secrets-manager', 'project': 'fixture-project',
                   'project_id': 'fixture-project-id', 'access': 'materialization only',
                   'bootstrap': {'store': 'gnome-keyring', 'service': 'fixture',
                                 'credential': 'fixture-token'}},
        'destination_root': str(root),
        'consumers': {'alpha': {'description': 'fixture consumer', 'destination': 'alpha.env',
                                'mode': '0600', 'service': None,
                                'secrets': [{'key': 'ALPHA_API_KEY', 'source_key': 'ALPHA_API_KEY',
                                             'source_id': None, 'minimum_length': 20}]}}}
    document.update(changes)
    return document


def fake_subprocess(project_rows, *, token=TOKEN, list_fails=False, by_id=None):
    def run(command, **kwargs):
        if command[0] == 'secret-tool':
            return SimpleNamespace(returncode=0 if token else 1, stdout=token or '', stderr='')
        if command[1:3] == ['secret', 'get']:
            return SimpleNamespace(returncode=0, stdout=json.dumps((by_id or {})[command[3]]), stderr='')
        if list_fails:
            return SimpleNamespace(returncode=1, stdout='', stderr='suppressed')
        # The bootstrap token is passed through the child environment, never argv.
        assert kwargs['env']['BWS_ACCESS_TOKEN'] == token
        assert not any(token in str(part) for part in command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(project_rows), stderr='')
    return run


class DeclarationTests(unittest.TestCase):
    def test_valid_declarations_load(self):
        with tempfile.TemporaryDirectory() as directory:
            document = declarations(directory)
            self.assertEqual(list(document['consumers']), ['alpha'])
            self.assertEqual(secrets.destination_root(document), Path(directory))

    def test_the_committed_declarations_are_valid_and_carry_no_values(self):
        document = secrets.load_declarations()
        self.assertIn('jev', document['consumers'])
        jev = document['consumers']['jev']
        self.assertEqual([entry['key'] for entry in jev['secrets']], ['TYPESAFE_API_KEY'])
        # Declarations carry names, locations and constraints, never material.
        allowed = {'key', 'source_key', 'source_id', 'minimum_length'}
        for consumer in document['consumers'].values():
            for entry in consumer['secrets']:
                self.assertLessEqual(set(entry), allowed)
                self.assertIsNone(entry['source_id'])
        def strings(node):
            if isinstance(node, dict):
                for name, child in node.items():
                    yield from ((name, text) for _, text in strings(child))
            elif isinstance(node, list):
                for child in node:
                    yield from strings(child)
            elif isinstance(node, str):
                yield None, node
        for name, value in strings(document):
            with self.subTest(name=name):
                self.assertNotIn('value', (name or '').lower())

    def test_unsafe_declarations_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            for change in ({'version': 2},
                           {'consumers': {'alpha': {'destination': '../escape.env', 'mode': '0600',
                                                    'secrets': [{'key': 'A_B_C'}], 'service': None}}},
                           {'consumers': {'alpha': {'destination': 'a.env', 'mode': '0644',
                                                    'secrets': [{'key': 'A_B_C'}], 'service': None}}},
                           {'consumers': {'alpha': {'destination': 'a.env', 'mode': '0600',
                                                    'secrets': [], 'service': None}}},
                           {'consumers': {'alpha': {'destination': 'a.env', 'mode': '0600',
                                                    'secrets': [{'key': 'lower'}], 'service': None}}},
                           {'consumers': {'Bad Name': {'destination': 'a.env', 'mode': '0600',
                                                       'secrets': [{'key': 'A_B_C'}], 'service': None}}}):
                with self.subTest(change=change):
                    path = Path(directory) / 'declaration.json'
                    path.write_text(json.dumps(declarations(directory, **change)))
                    with self.assertRaises((secrets.MaterializationError, KeyError)):
                        secrets.load_declarations(path)


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.document = declarations(self.root)
        self.path = self.root / 'alpha.env'
        self.addCleanup(self.directory.cleanup)

    def materialize(self, rows, **kwargs):
        with patch.object(secrets.subprocess, 'run', fake_subprocess(rows, **kwargs)):
            return secrets.materialize(self.document, 'alpha')

    def test_only_declared_secrets_are_written(self):
        report = self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE},
                                   {'key': 'UNRELATED_KEY', 'value': OTHER}])
        self.assertEqual(report['outcome'], 'written')
        self.assertTrue(report['safe'])
        body = self.path.read_text()
        self.assertEqual(body, f'ALPHA_API_KEY={VALUE}\n')
        self.assertNotIn(OTHER, body)
        self.assertEqual(report['undeclared_keys'], [])

    def test_credential_permissions_are_owner_only(self):
        self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE}])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(self.path.stat().st_uid, os.getuid())

    def test_absent_empty_and_placeholder_secrets_are_refused(self):
        for rows in ([{'key': 'SOMETHING_ELSE', 'value': VALUE}],
                     [{'key': 'ALPHA_API_KEY', 'value': ''}],
                     [{'key': 'ALPHA_API_KEY', 'value': 'short'}],
                     [{'key': 'ALPHA_API_KEY', 'value': 'replace-me-with-a-real-key'}],
                     [{'key': 'ALPHA_API_KEY', 'value': 'has space in value 0123456789'}],
                     [{'key': 'ALPHA_API_KEY', 'value': VALUE}, {'key': 'ALPHA_API_KEY', 'value': OTHER}]):
            with self.subTest(rows=rows), self.assertRaises(secrets.MaterializationError):
                self.materialize(rows)
            self.assertFalse(self.path.exists())

    def test_a_failure_never_replaces_a_valid_existing_credential(self):
        self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE}])
        original = self.path.read_text()
        for rows, kwargs in (([{'key': 'ALPHA_API_KEY', 'value': ''}], {}),
                             ([], {}),
                             ([{'key': 'ALPHA_API_KEY', 'value': VALUE}], {'list_fails': True}),
                             ([{'key': 'ALPHA_API_KEY', 'value': VALUE}], {'token': ''})):
            with self.subTest(rows=rows), self.assertRaises(secrets.MaterializationError):
                self.materialize(rows, **kwargs)
            self.assertEqual(self.path.read_text(), original)
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_rotation_replaces_atomically_and_repeats_are_no_ops(self):
        self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE}])
        repeated = self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE}])
        self.assertEqual(repeated['outcome'], 'unchanged')
        rotated = self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE + 'rotated'}])
        self.assertEqual(rotated['outcome'], 'written')
        self.assertIn('rotated', self.path.read_text())
        self.assertEqual(list(self.root.glob('.blaine-secret-*')), [])

    def test_targeted_retrieval_by_identity_avoids_project_enumeration(self):
        self.document['consumers']['alpha']['secrets'][0]['source_id'] = 'fixture-id'
        report = self.materialize([], by_id={'fixture-id': {'key': 'ALPHA_API_KEY', 'value': VALUE}},
                                  list_fails=True)
        self.assertEqual(report['outcome'], 'written')

    def test_a_symlinked_destination_is_refused(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        (self.root / 'elsewhere.env').write_text('x')
        self.path.symlink_to(self.root / 'elsewhere.env')
        with self.assertRaises(secrets.MaterializationError):
            self.materialize([{'key': 'ALPHA_API_KEY', 'value': VALUE}])


class RuntimeConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.document = declarations(self.root)
        self.path = self.root / 'alpha.env'
        self.addCleanup(self.directory.cleanup)
        with patch.object(secrets.subprocess, 'run',
                          fake_subprocess([{'key': 'ALPHA_API_KEY', 'value': VALUE}])):
            secrets.materialize(self.document, 'alpha')

    def test_runtime_load_never_touches_the_secret_manager(self):
        def forbidden(*args, **kwargs):
            raise AssertionError('runtime must not invoke the secret manager')
        with patch.object(secrets.subprocess, 'run', forbidden):
            values = secrets.load(self.document, 'alpha')
        self.assertEqual(values, {'ALPHA_API_KEY': VALUE})

    def test_an_unsafe_or_incomplete_credential_is_refused_at_runtime(self):
        self.path.chmod(0o644)
        with self.assertRaises(secrets.MaterializationError):
            secrets.load(self.document, 'alpha')
        self.path.chmod(0o600)
        self.path.write_text(f'ALPHA_API_KEY={VALUE}\nUNDECLARED_KEY={OTHER}\n')
        with self.assertRaises(secrets.MaterializationError):
            secrets.load(self.document, 'alpha')
        self.path.unlink()
        with self.assertRaises(secrets.MaterializationError):
            secrets.load(self.document, 'alpha')

    def test_status_and_verify_report_state_without_values(self):
        report = secrets.inspect(self.path, self.document['consumers']['alpha']['secrets'])
        self.assertTrue(report['safe'])
        self.assertEqual(report['mode'], '0600')
        self.assertEqual(report['keys'], ['ALPHA_API_KEY'])
        self.assertNotIn(VALUE, json.dumps(report))

    def test_failures_and_reports_never_carry_a_value(self):
        self.path.write_text(f'ALPHA_API_KEY={VALUE}\nUNDECLARED_KEY={OTHER}\n')
        try:
            secrets.load(self.document, 'alpha')
        except secrets.MaterializationError as error:
            self.assertNotIn(VALUE, str(error))
            self.assertNotIn(OTHER, str(error))
        with patch.object(secrets.subprocess, 'run',
                          fake_subprocess([{'key': 'ALPHA_API_KEY', 'value': 'bad value here!'}])):
            try:
                secrets.materialize(self.document, 'alpha')
            except secrets.MaterializationError as error:
                self.assertNotIn('bad value here!', str(error))

    def test_a_launched_consumer_sees_only_its_declared_secrets(self):
        self.document['consumers']['beta'] = {
            'description': 'second fixture consumer', 'destination': 'beta.env', 'mode': '0600',
            'service': None, 'secrets': [{'key': 'BETA_API_KEY', 'source_key': 'BETA_API_KEY',
                                          'source_id': None, 'minimum_length': 20}]}
        environment = {'BETA_API_KEY': OTHER, 'BWS_ACCESS_TOKEN': TOKEN,
                       'PATH': os.environ.get('PATH', '')}
        captured = {}

        def fake_exec(program, argv, env):
            captured.update(program=program, argv=argv, env=env)
        with patch.dict(os.environ, environment, clear=True), patch.object(secrets.os, 'execvpe', fake_exec):
            secrets.run(self.document, 'alpha', ['fixture-command', '--flag'])
        self.assertEqual(captured['env']['ALPHA_API_KEY'], VALUE)
        # Another consumer's inherited secret is stripped before exec, and so is
        # authority over the secret manager itself.
        self.assertNotIn('BETA_API_KEY', captured['env'])
        self.assertNotIn('BWS_ACCESS_TOKEN', captured['env'])
        self.assertNotIn(TOKEN, json.dumps(captured['env']))
        self.assertNotIn(VALUE, ' '.join(captured['argv']))


if __name__ == '__main__':
    unittest.main()

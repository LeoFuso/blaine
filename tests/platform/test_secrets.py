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
RESOLVER_BODY = b'#!/bin/sh\nexit 0\n'
RESOLVER_DIGEST = __import__('hashlib').sha256(RESOLVER_BODY).hexdigest()


def fixture_resolver(root):
    """A pinned stand-in binary; the fake never executes it."""
    path = Path(root) / 'secretspec'
    path.write_bytes(RESOLVER_BODY)
    path.chmod(0o755)
    return path


def fixture_manifest(root, keys=('ALPHA_API_KEY',)):
    manifests = Path(root) / 'manifests'
    manifests.mkdir(exist_ok=True)
    body = '[project]\nname = "fixture"\n\n[profiles.default]\n'
    body += ''.join(f'{key} = {{ description = "fixture", required = true }}\n' for key in keys)
    (manifests / 'alpha.toml').write_text(body)
    return manifests


def declarations(root, **changes):
    document = {
        'version': 2,
        'resolver': {'engine': 'secretspec', 'version': '0.20.0',
                     'executable': str(fixture_resolver(root)), 'sha256': RESOLVER_DIGEST,
                     'provider_alias': 'runtime_secrets',
                     'manifest_root': str(fixture_manifest(root)),
                     'access': 'materialization only'},
        'source': {'provider': 'bitwarden-secrets-manager', 'project': 'fixture-project',
                   'project_id': 'fixture-project-id', 'access': 'materialization only',
                   'bootstrap': {'store': 'gnome-keyring', 'service': 'fixture',
                                 'credential': 'fixture-token'}},
        'destination_root': str(root),
        'consumers': {'alpha': {'description': 'fixture consumer', 'destination': 'alpha.env',
                                'mode': '0600', 'service': None, 'manifest': 'alpha.toml',
                                'restart_on_rotation': False,
                                'secrets': [{'key': 'ALPHA_API_KEY', 'minimum_length': 20}]}}}
    document.update(changes)
    return document


def fake_subprocess(resolved, *, token=TOKEN, resolver_fails=False):
    """Fakes the keyring bootstrap and the SecretSpec export; no process runs."""
    def run(command, **kwargs):
        if command[0] == 'secret-tool':
            return SimpleNamespace(returncode=0 if token else 1, stdout=token or '', stderr='')
        if resolver_fails:
            return SimpleNamespace(returncode=1, stdout='', stderr='suppressed')
        # The bootstrap token reaches the resolver's environment, never its argv.
        assert kwargs['env']['BWS_ACCESS_TOKEN'] == token
        assert not any(token in str(part) for part in command)
        assert '--provider' in command and 'runtime_secrets' in command
        body = ''.join(f"export {key}='{value}'\n" for key, value in resolved.items())
        return SimpleNamespace(returncode=0, stdout=body, stderr='')
    return run


class DeclarationTests(unittest.TestCase):
    def test_valid_declarations_load(self):
        with tempfile.TemporaryDirectory() as directory:
            document = declarations(directory)
            self.assertEqual(list(document['consumers']), ['alpha'])
            self.assertEqual(secrets.destination_root(document), Path(directory))

    def test_the_committed_declarations_are_valid_and_carry_no_values(self):
        document = secrets.load_declarations()
        self.assertEqual(document['resolver']['engine'], 'secretspec')
        self.assertIn('jev', document['consumers'])
        jev = document['consumers']['jev']
        self.assertEqual([entry['key'] for entry in jev['secrets']], ['TYPESAFE_API_KEY'])
        # Declarations carry names, locations and constraints, never material.
        allowed = {'key', 'minimum_length'}
        for consumer in document['consumers'].values():
            for entry in consumer['secrets']:
                self.assertLessEqual(set(entry), allowed)
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
            for change in ({'version': 1},
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

    def materialize(self, resolved, **kwargs):
        with patch.object(secrets.subprocess, 'run', fake_subprocess(resolved, **kwargs)):
            return secrets.materialize(self.document, 'alpha')

    def test_only_declared_secrets_are_written(self):
        # An over-resolving backend must not widen the consumer's credential.
        report = self.materialize({'ALPHA_API_KEY': VALUE, 'UNRELATED_KEY': OTHER})
        self.assertEqual(report['outcome'], 'written')
        self.assertTrue(report['safe'])
        body = self.path.read_text()
        self.assertEqual(body, f'ALPHA_API_KEY={VALUE}\n')
        self.assertNotIn(OTHER, body)
        self.assertEqual(report['undeclared_keys'], [])

    def test_credential_permissions_are_owner_only(self):
        self.materialize({'ALPHA_API_KEY': VALUE})
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.path.parent.stat().st_mode), 0o700)
        self.assertEqual(self.path.stat().st_uid, os.getuid())

    def test_absent_empty_and_placeholder_secrets_are_refused(self):
        for resolved in ({'SOMETHING_ELSE': VALUE}, {'ALPHA_API_KEY': ''},
                         {'ALPHA_API_KEY': 'short'},
                         {'ALPHA_API_KEY': 'replace-me-with-a-real-key'},
                         {'ALPHA_API_KEY': 'has space in value 0123456789'}, {}):
            with self.subTest(resolved=resolved), self.assertRaises(secrets.MaterializationError):
                self.materialize(resolved)
            self.assertFalse(self.path.exists())

    def test_a_failure_never_replaces_a_valid_existing_credential(self):
        self.materialize({'ALPHA_API_KEY': VALUE})
        original = self.path.read_text()
        for resolved, kwargs in (({'ALPHA_API_KEY': ''}, {}), ({}, {}),
                                 ({'ALPHA_API_KEY': VALUE}, {'resolver_fails': True}),
                                 ({'ALPHA_API_KEY': VALUE}, {'token': ''})):
            with self.subTest(resolved=resolved), self.assertRaises(secrets.MaterializationError):
                self.materialize(resolved, **kwargs)
            self.assertEqual(self.path.read_text(), original)
            self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_rotation_replaces_atomically_and_repeats_are_no_ops(self):
        self.materialize({'ALPHA_API_KEY': VALUE})
        repeated = self.materialize({'ALPHA_API_KEY': VALUE})
        self.assertEqual(repeated['outcome'], 'unchanged')
        self.assertFalse(repeated['rotation']['value_changed'])
        rotated = self.materialize({'ALPHA_API_KEY': VALUE + 'rotated'})
        self.assertEqual(rotated['outcome'], 'written')
        # Rotation is not a reload: already-running processes keep the old value.
        self.assertTrue(rotated['rotation']['value_changed'])
        self.assertTrue(rotated['rotation']['running_processes_keep_previous_value_until_restarted'])
        self.assertFalse(rotated['rotation']['restart_required'])
        self.assertIn('rotated', self.path.read_text())
        self.assertEqual(list(self.root.glob('.blaine-secret-*')), [])

    def test_an_unpinned_resolver_is_never_executed(self):
        Path(self.document['resolver']['executable']).write_bytes(b'#!/bin/sh\nexit 1\n')
        with self.assertRaises(secrets.MaterializationError):
            self.materialize({'ALPHA_API_KEY': VALUE})
        self.document['resolver']['executable'] = str(self.root / 'absent-resolver')
        with self.assertRaises(secrets.MaterializationError):
            self.materialize({'ALPHA_API_KEY': VALUE})

    def test_manifest_and_declaration_must_agree(self):
        manifests = Path(self.document['resolver']['manifest_root'])
        (manifests / 'alpha.toml').write_text(
            '[project]\nname = "fixture"\n\n[profiles.default]\n'
            'ALPHA_API_KEY = { required = true }\nEXTRA_KEY = { required = true }\n')
        with self.assertRaises(secrets.MaterializationError):
            self.materialize({'ALPHA_API_KEY': VALUE})
        self.assertFalse(self.path.exists())

    def test_a_symlinked_destination_is_refused(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        (self.root / 'elsewhere.env').write_text('x')
        self.path.symlink_to(self.root / 'elsewhere.env')
        with self.assertRaises(secrets.MaterializationError):
            self.materialize({'ALPHA_API_KEY': VALUE})


class RuntimeConsumptionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.document = declarations(self.root)
        self.path = self.root / 'alpha.env'
        self.addCleanup(self.directory.cleanup)
        with patch.object(secrets.subprocess, 'run', fake_subprocess({'ALPHA_API_KEY': VALUE})):
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
                          fake_subprocess({'ALPHA_API_KEY': 'bad value here!'})):
            try:
                secrets.materialize(self.document, 'alpha')
            except secrets.MaterializationError as error:
                self.assertNotIn('bad value here!', str(error))

    def test_a_launched_consumer_sees_only_its_declared_secrets(self):
        self.document['consumers']['beta'] = {
            'description': 'second fixture consumer', 'destination': 'beta.env', 'mode': '0600',
            'service': None, 'manifest': 'beta.toml', 'restart_on_rotation': False,
            'secrets': [{'key': 'BETA_API_KEY', 'minimum_length': 20}]}
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

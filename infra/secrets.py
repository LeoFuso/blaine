#!/usr/bin/env python3
"""Explicit secret materialization: Bitwarden -> local consumer credential -> runtime.

Bitwarden Secrets Manager is where Blaine secrets are managed. It is not a runtime
dependency, and neither is GNOME Keyring, which only holds the bootstrap machine
credential. Remote access happens here, during an operator-invoked materialization
or rotation, and nowhere else. A service or provider reads only the local
consumer-specific credential it was declared to receive.

    bitwarden -> materialize (operator, explicit) -> local 0600 credential
              -> systemd service / bounded process -> runtime

No secret value is printed, logged, placed in a process argument, or written to
evidence. Diagnostics are deliberately coarse: a provider or validation message
can quote the value it rejected.

This is a materialization client, not a secret manager. It runs no daemon, adds
no server, implements no cryptography, and stores nothing beyond the declared
consumer credentials.
"""
import argparse
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
# Declarations live outside any directory named `secrets/`, which .gitignore
# protects, so no value can be committed by loosening that rule.
DECLARATIONS = ROOT / 'secret-consumers.json'
# Shell-hostile characters are refused so a credential file stays a safe
# KEY=value environment file that systemd and a launcher can both consume.
FORBIDDEN = re.compile(r'[\s\x00-\x1f\x7f"\'`$\\]')
PLACEHOLDERS = ('placeholder', 'replace', 'changeme', 'example', 'your-key')
# Authority over the secret manager must never reach a consumer, even when an
# operator shell happens to export it. A consumer gets its declared values only.
BOOTSTRAP_VARIABLES = ('BWS_ACCESS_TOKEN', 'BWS_SERVER_URL', 'BWS_IDENTITY_URL',
                       'BW_SESSION', 'SECRETSPEC_PROVIDER')
KEY = re.compile(r'[A-Z][A-Z0-9_]{2,63}')


class MaterializationError(RuntimeError):
    """Bounded failure. It never carries a secret value or provider text."""


def load_declarations(path: Path = DECLARATIONS) -> dict:
    document = json.loads(path.read_text())
    if document.get('version') != 1:
        raise MaterializationError('Unsupported declaration version')
    for name, consumer in document['consumers'].items():
        if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}', name):
            raise MaterializationError('Invalid consumer name')
        destination = consumer['destination']
        if '/' in destination or destination.startswith('.'):
            raise MaterializationError('Consumer destination must be a plain file name')
        if consumer['mode'] != '0600':
            raise MaterializationError('Consumer credentials must be operator-only')
        if not consumer['secrets'] or len(consumer['secrets']) > 16:
            raise MaterializationError('A consumer declares between one and sixteen secrets')
        keys = [entry['key'] for entry in consumer['secrets']]
        if len(set(keys)) != len(keys) or not all(KEY.fullmatch(key) for key in keys):
            raise MaterializationError('Invalid or duplicated declared key')
    return document


def destination_root(document: dict) -> Path:
    return Path(document['destination_root']).expanduser()


def bootstrap_token(document: dict) -> str:
    """Read the machine-account bootstrap credential, only during materialization."""
    source = document['source']['bootstrap']
    if source['store'] != 'gnome-keyring':
        raise MaterializationError('Unsupported bootstrap store')
    result = subprocess.run(['secret-tool', 'lookup', 'service', source['service'],
                             'credential', source['credential']],
                            capture_output=True, text=True, timeout=20)
    token = result.stdout.strip()
    if result.returncode or not token:
        raise MaterializationError('Bootstrap credential unavailable; diagnostics suppressed')
    return token


def fetch(document: dict, wanted: list[dict]) -> dict:
    """Retrieve exactly the declared secrets. The whole project is never exported.

    A declaration carrying a non-secret `source_id` is retrieved by identity;
    otherwise the value is resolved by key. Only declared keys are returned, so a
    project-wide read can never become a consumer's environment.
    """
    environment = dict(os.environ, BWS_ACCESS_TOKEN=bootstrap_token(document))
    project = document['source']['project_id']
    values, pending = {}, []
    for entry in wanted:
        if entry.get('source_id'):
            result = subprocess.run(['/usr/local/bin/bws', 'secret', 'get', entry['source_id']],
                                    env=environment, capture_output=True, text=True, timeout=45)
            if result.returncode:
                raise MaterializationError('Targeted secret read failed; diagnostics suppressed')
            values[entry['key']] = json.loads(result.stdout).get('value')
        else:
            pending.append(entry)
    if pending:
        result = subprocess.run(['/usr/local/bin/bws', 'secret', 'list', project],
                                env=environment, capture_output=True, text=True, timeout=45)
        if result.returncode:
            raise MaterializationError('Project secret read failed; diagnostics suppressed')
        by_key = {}
        for row in json.loads(result.stdout):
            if row.get('key') in {entry['source_key'] for entry in pending}:
                if row['key'] in by_key:
                    raise MaterializationError('Declared key is ambiguous in the source project')
                by_key[row['key']] = row.get('value')
        for entry in pending:
            if entry['source_key'] not in by_key:
                raise MaterializationError('Declared secret absent from the source project')
            values[entry['key']] = by_key[entry['source_key']]
    return values


def validate(values: dict, wanted: list[dict]) -> dict:
    declared = {entry['key'] for entry in wanted}
    if set(values) != declared:
        raise MaterializationError('Retrieved keys do not match the declaration exactly')
    for entry in wanted:
        value = values[entry['key']]
        if not isinstance(value, str) or not value:
            raise MaterializationError('Declared secret is empty')
        if FORBIDDEN.search(value):
            raise MaterializationError('Declared secret contains unsupported characters')
        if len(value) < entry.get('minimum_length', 1):
            raise MaterializationError('Declared secret is shorter than its declared minimum')
        if any(marker in value.lower() for marker in PLACEHOLDERS):
            raise MaterializationError('Declared secret looks like a placeholder')
    return values


def render(values: dict, wanted: list[dict]) -> str:
    # Deterministic declaration order, so re-materializing identical values is a no-op.
    return ''.join(f"{entry['key']}={values[entry['key']]}\n" for entry in wanted)


def write_atomically(path: Path, content: str) -> str:
    """Replace only after the complete new credential exists on disk.

    A partially written or failed materialization therefore leaves a previously
    valid credential untouched.
    """
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise MaterializationError('Refusing a symlinked credential path')
    if path.exists():
        current = path.stat()
        if not stat.S_ISREG(current.st_mode) or current.st_uid != os.getuid():
            raise MaterializationError('Existing credential is not an operator-owned regular file')
        if path.read_text() == content and stat.S_IMODE(current.st_mode) == 0o600:
            return 'unchanged'
    handle, temporary = tempfile.mkstemp(prefix='.blaine-secret-', dir=path.parent)
    try:
        os.fchmod(handle, 0o600)
        with os.fdopen(handle, 'w') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return 'written'


def inspect(path: Path, wanted: list[dict]) -> dict:
    """Report presence, permissions and declared keys. Values are never returned."""
    if not path.exists():
        return {'present': False, 'mode': None, 'keys': [], 'undeclared_keys': [],
                'missing_keys': sorted(entry['key'] for entry in wanted), 'safe': False}
    mode = stat.S_IMODE(path.stat().st_mode)
    keys = [line.split('=', 1)[0] for line in path.read_text().splitlines() if line]
    declared = {entry['key'] for entry in wanted}
    undeclared = sorted(set(keys) - declared)
    missing = sorted(declared - set(keys))
    return {'present': True, 'mode': f'{mode:04o}', 'keys': sorted(keys),
            'undeclared_keys': undeclared, 'missing_keys': missing,
            'owner_only': mode == 0o600 and path.stat().st_uid == os.getuid(),
            'safe': mode == 0o600 and not undeclared and not missing}


def consumer_of(document: dict, name: str) -> tuple[dict, Path]:
    if name not in document['consumers']:
        raise MaterializationError('Unknown consumer')
    consumer = document['consumers'][name]
    return consumer, destination_root(document) / consumer['destination']


def materialize(document: dict, name: str) -> dict:
    consumer, path = consumer_of(document, name)
    wanted = consumer['secrets']
    values = validate(fetch(document, wanted), wanted)
    outcome = write_atomically(path, render(values, wanted))
    report = inspect(path, wanted)
    if not report['safe']:
        raise MaterializationError('Materialized credential failed its own verification')
    return {'consumer': name, 'outcome': outcome, 'path': str(path), **report}


def load(document: dict, name: str) -> dict:
    """Runtime read of an already-materialized credential. No remote access."""
    consumer, path = consumer_of(document, name)
    report = inspect(path, consumer['secrets'])
    if not report['present']:
        raise MaterializationError('Consumer credential has not been materialized')
    if not report['safe']:
        raise MaterializationError('Consumer credential is unsafe or incomplete')
    values = {}
    for line in path.read_text().splitlines():
        if line:
            key, _, value = line.partition('=')
            values[key] = value
    return values


def run(document: dict, name: str, command: list[str]) -> int:
    """Exec a bounded consumer with only its declared credentials added.

    The credential never appears in an argument, and no other consumer's secrets
    are visible to the child process.
    """
    if not command:
        raise MaterializationError('A command is required')
    withheld = set(BOOTSTRAP_VARIABLES) | {entry['key'] for consumer in document['consumers'].values()
                                           for entry in consumer['secrets']}
    environment = {k: v for k, v in os.environ.items() if k not in withheld}
    os.execvpe(command[0], command, environment | load(document, name))


def main() -> int:
    parser = argparse.ArgumentParser(description='Explicit Blaine secret materialization')
    parser.add_argument('--declarations', type=Path, default=DECLARATIONS)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('status', help='report declared consumers and local credential state')
    for name in ('materialize', 'verify'):
        sub = commands.add_parser(name)
        sub.add_argument('consumer')
    launcher = commands.add_parser('run', help='exec a command with one consumer credential')
    launcher.add_argument('consumer')
    launcher.add_argument('argv', nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    document = load_declarations(arguments.declarations)
    try:
        if arguments.command == 'status':
            report = {'project': document['source']['project'],
                      'remote_access': document['source']['access'],
                      'destination_root': str(destination_root(document)),
                      'consumers': {name: inspect(destination_root(document) / consumer['destination'],
                                                  consumer['secrets'])
                                    for name, consumer in document['consumers'].items()}}
        elif arguments.command == 'materialize':
            report = materialize(document, arguments.consumer)
        elif arguments.command == 'verify':
            consumer, path = consumer_of(document, arguments.consumer)
            report = {'consumer': arguments.consumer, 'path': str(path),
                      **inspect(path, consumer['secrets'])}
        else:
            argv = [x for x in arguments.argv if x != '--']
            return run(document, arguments.consumer, argv)
    except MaterializationError as error:
        print(json.dumps({'outcome': 'FAILED', 'reason': str(error)}, indent=1))
        return 1
    print(json.dumps(report, indent=1))
    return 0 if report.get('safe', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())

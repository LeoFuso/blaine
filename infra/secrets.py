#!/usr/bin/env python3
"""Explicit secret materialization: remote backend -> local credential -> runtime.

SecretSpec owns provider resolution behind a single alias, so the remote backend
can change without touching Blaine. Blaine owns what is genuinely its own: the
consumer allowlist, the destination, restrictive atomic activation, verification
and rotation reporting.

    remote backend -> secretspec (alias) -> materialize (operator, explicit)
                   -> local 0600 credential -> service / bounded process -> runtime

The remote backend is not a runtime dependency, and neither is GNOME Keyring,
which only holds the bootstrap machine credential. Remote access happens here,
during an operator-invoked materialization or rotation, and nowhere else.

No secret value is printed, logged, placed in a process argument, or written to
evidence. Diagnostics are deliberately coarse: a provider or validation message
can quote the value it rejected.

Each consumer owns a separate SecretSpec manifest. SecretSpec profiles extend the
default profile rather than isolating from it, so a shared manifest would let one
consumer resolve another consumer's secrets; separate manifests plus Blaine's own
allowlist keep least-secret delivery true rather than assumed.

This is a materialization client, not a secret manager. It runs no daemon, adds
no server, implements no cryptography, and stores nothing beyond the declared
consumer credentials.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent  # manifest paths in the declaration are repository-relative
# Declarations live outside any directory named `secrets/`, which .gitignore
# protects, so no value can be committed by loosening that rule.
DECLARATIONS = ROOT / 'secret-consumers.json'
# Shell-hostile characters are refused so a credential file stays a safe
# KEY=value environment file that systemd and a launcher can both consume.
FORBIDDEN = re.compile(r'[\s\x00-\x1f\x7f"\'`$\\]')
PLACEHOLDERS = ('placeholder', 'replace', 'changeme', 'example', 'your-key')
# SecretSpec 0.20 refuses agent-driven resolution without a recorded reason, and
# writes it to its local audit log. Stating it here keeps that record truthful.
REASON = 'Blaine operator-invoked consumer credential materialization'
# Authority over the secret manager must never reach a consumer, even when an
# operator shell happens to export it. A consumer gets its declared values only.
BOOTSTRAP_VARIABLES = ('BWS_ACCESS_TOKEN', 'BWS_SERVER_URL', 'BWS_IDENTITY_URL',
                       'BW_SESSION', 'SECRETSPEC_PROVIDER')
KEY = re.compile(r'[A-Z][A-Z0-9_]{2,63}')


class MaterializationError(RuntimeError):
    """Bounded failure. It never carries a secret value or provider text."""


def load_declarations(path: Path = DECLARATIONS) -> dict:
    document = json.loads(path.read_text())
    if document.get('version') != 2:
        raise MaterializationError('Unsupported declaration version')
    resolver = document['resolver']
    if resolver['engine'] != 'secretspec':
        raise MaterializationError('Unsupported resolver engine')
    if not re.fullmatch(r'[a-z][a-z0-9_]{2,39}', resolver['provider_alias']):
        raise MaterializationError('Invalid provider alias')
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
        manifest = consumer['manifest']
        if '/' in manifest or not manifest.endswith('.toml'):
            raise MaterializationError('Consumer manifest must be a plain file name')
    return document


def resolver_executable(document: dict) -> Path:
    """Use the pinned resolver only. An unexpected binary is never executed."""
    resolver = document['resolver']
    path = Path(resolver['executable']).expanduser()
    if not path.is_file():
        raise MaterializationError('Pinned resolver is not installed')
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != resolver['sha256']:
        raise MaterializationError('Resolver binary does not match its pinned digest')
    return path


def manifest_keys(path: Path) -> set[str]:
    """Declared keys in a SecretSpec manifest, read without a TOML dependency.

    Only key names are parsed; the file contains no values by construction.
    """
    keys, profile = set(), None
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith('[') and stripped.endswith(']'):
            profile = stripped[1:-1]
        elif profile == 'profiles.default' and '=' in stripped and not stripped.startswith('#'):
            keys.add(stripped.split('=', 1)[0].strip())
    return keys


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


def fetch(document: dict, consumer: dict, wanted: list[dict]) -> dict:
    """Resolve exactly the declared secrets through the SecretSpec alias.

    The backend behind the alias is deployment configuration, so moving from one
    secret manager to another does not reach this code. The bootstrap credential
    is passed through the resolver's child environment, never an argument.
    """
    resolver = document['resolver']
    executable = resolver_executable(document)
    root = Path(resolver['manifest_root'])
    manifest = (root if root.is_absolute() else REPO / root) / consumer['manifest']
    declared = {entry['key'] for entry in wanted}
    if manifest_keys(manifest) != declared:
        raise MaterializationError('Consumer manifest and declaration disagree')
    environment = dict(os.environ, BWS_ACCESS_TOKEN=bootstrap_token(document))
    result = subprocess.run(
        [str(executable), '--file', str(manifest), '--reason', REASON,
         '--caller', 'blaine-materializer', '--caller-operation', 'materialize',
         'export', '--provider', resolver['provider_alias']],
        env=environment, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise MaterializationError('Secret resolution failed; diagnostics suppressed')
    values = {}
    for line in result.stdout.splitlines():
        if line.startswith('export '):
            key, _, value = line[len('export '):].partition('=')
            if key in declared:
                values[key] = value.strip("'")
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
    values = validate(fetch(document, consumer, wanted), wanted)
    outcome = write_atomically(path, render(values, wanted))
    report = inspect(path, wanted)
    if not report['safe']:
        raise MaterializationError('Materialized credential failed its own verification')
    # Rotation is not a reload. A process that already started holds the previous
    # value in its environment until it is restarted, so say so explicitly rather
    # than let a silent staleness window look like a completed rotation.
    rotation = {'value_changed': outcome == 'written', 'service': consumer['service'],
                'restart_required': bool(outcome == 'written' and consumer['service']),
                'running_processes_keep_previous_value_until_restarted': outcome == 'written'}
    return {'consumer': name, 'outcome': outcome, 'path': str(path),
            'resolver': document['resolver']['engine'], 'rotation': rotation, **report}


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
                      'resolver': document['resolver']['engine'] + ' ' + document['resolver']['version'],
                      'provider_alias': document['resolver']['provider_alias'],
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

"""Private Personal Agent deployment; optional operator-selected local adapters.

Policy C runs here with no escalation binding configured, so an escalation
recommendation is admissible only once an operator deploys one. Until then the
trusted boundary denies it and the Task stays local, which is recorded.
"""
import asyncio
import json
import os
from pathlib import Path

import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.execution import Capabilities
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.workflow import create_workflow


def no_unnecessary_cognition(packet):
    raise restate.TerminalError('No deterministic continuation; completion criteria remain unmet')


def target_effects(directory, deployment):
    """Operator-reviewed target provider and exec profiles (PA-3), or none.

    Only workspaces and profiles named in the deployment exist; a grant can
    select among them and nothing else. Absent configuration keeps the previous
    behaviour: every target effect is ``not_dispatched``.
    """
    workspaces = (deployment or {}).get('coding_workspaces') or {}
    if not workspaces:
        return None, None
    from runtime.kernel.effects import ExecProfile, validate_profile
    from runtime.kernel.target_local import LocalWorktreeProvider
    provider = LocalWorktreeProvider({name: spec['root'] for name, spec in workspaces.items()},
                                     directory / 'target.sqlite')
    profiles = {}
    for name, spec in (deployment.get('exec_profiles') or {}).items():
        profile = ExecProfile(id=name, executable=spec['executable'], args=tuple(spec.get('args', ())),
                              allowed_args=tuple(spec.get('allowed_args', ())),
                              timeout_seconds=spec.get('timeout_seconds', 120.0),
                              poll_seconds=spec.get('poll_seconds', 1.0),
                              output_cap_bytes=spec.get('output_cap_bytes', 65536))
        validate_profile(profile.payload())
        profiles[name] = profile
    return provider, profiles


def application(directory, deployment=None):
    store = ArtifactStore(directory / 'artifacts')
    target_provider, exec_profiles = target_effects(directory, deployment)
    cognitive, worker, providers = no_unnecessary_cognition, None, []
    if deployment is not None:
        from runtime.kernel.model import LocalModelCognition
        from runtime.kernel.memory import MirixContext
        from runtime.kernel.worker import GooseWorker
        cognitive = LocalModelCognition(**deployment['cognition'])
        providers = [MirixContext(**deployment['memory'])]
        worker = GooseWorker(Path(deployment['goose']), directory / 'workers',
                             model=deployment['cognition']['model'])
    return restate.app([create_workflow(store, cognitive,
        Capabilities(store, directory / 'fixture.sqlite', worker=worker), providers=providers,
        event_publisher=JsonlEventPublisher(directory / 'events.jsonl'),
        target_provider=target_provider, exec_profiles=exec_profiles)])


if __name__ == '__main__':
    config = Config()
    config.bind = ['127.0.0.1:49080']
    deployment_path = os.environ.get('BLAINE_DEPLOYMENT_CONFIG')
    deployment = json.loads(Path(deployment_path).read_text()) if deployment_path else None
    asyncio.run(serve(application(Path(os.environ.get('BLAINE_D2_DATA', '.local/d2')), deployment), config))

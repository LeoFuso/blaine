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


def application(directory, deployment=None):
    store = ArtifactStore(directory / 'artifacts')
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
        event_publisher=JsonlEventPublisher(directory / 'events.jsonl'))])


if __name__ == '__main__':
    config = Config()
    config.bind = ['127.0.0.1:49080']
    deployment_path = os.environ.get('BLAINE_DEPLOYMENT_CONFIG')
    deployment = json.loads(Path(deployment_path).read_text()) if deployment_path else None
    asyncio.run(serve(application(Path(os.environ.get('BLAINE_D2_DATA', '.local/d2')), deployment), config))

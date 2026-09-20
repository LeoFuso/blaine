"""Private D2 deployment of the existing kernel. No frontier/model adapter."""
import asyncio
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


def application(directory):
    store = ArtifactStore(directory / 'artifacts')
    return restate.app([create_workflow(store, no_unnecessary_cognition,
        Capabilities(store, directory / 'fixture.sqlite'),
        event_publisher=JsonlEventPublisher(directory / 'events.jsonl'))])


if __name__ == '__main__':
    config = Config()
    config.bind = ['127.0.0.1:49080']
    asyncio.run(serve(application(Path(os.environ.get('BLAINE_D2_DATA', '.local/d2'))), config))

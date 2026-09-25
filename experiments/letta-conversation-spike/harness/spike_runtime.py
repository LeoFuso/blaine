#!/usr/bin/env python3
"""Serve the unchanged `runtime.personal_runtime.application` on a spike port.

`python -m runtime.personal_runtime` hardcodes the canonical 127.0.0.1:49080, so
the spike binds the same application object elsewhere. No deployment config:
the D2 shapes used here (text.stats summarize, human.request decision) are
deterministic and need no cognition, MIRIX or Goose.
"""
import asyncio
import os
import sys
from pathlib import Path

from hypercorn.asyncio import serve
from hypercorn.config import Config

from runtime.personal_runtime import application

if __name__ == '__main__':
    data = Path(os.environ['SPIKE_BLAINE_DATA'])
    data.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.bind = [f"127.0.0.1:{os.environ.get('SPIKE_RUNTIME_PORT', '59080')}"]
    print('spike runtime', config.bind, data, file=sys.stderr, flush=True)
    asyncio.run(serve(application(data), config))

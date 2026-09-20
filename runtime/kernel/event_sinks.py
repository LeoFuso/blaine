"""Acceptance/local forensic JSONL sink, not the target observability backend."""
import fcntl
import json
import os
from pathlib import Path

from runtime.kernel.contracts import encode
from runtime.kernel.events import ExecutionEvent, validate_event


class JsonlEventPublisher:
    def __init__(self, path: Path):
        self.path = path

    def publish(self, event: ExecutionEvent) -> None:
        record = encode(validate_event(event)) + b'\n'
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # File itself is the small acceptance sink; no secondary store/index.
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o600)
        with os.fdopen(fd, 'r+b') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            for line in stream:
                prior = json.loads(line)
                if prior['event_id'] == event['event_id']:
                    if encode(prior) != encode(event):
                        raise ValueError('Conflicting event identity')
                    return  # crash after append / before journal acknowledgement
            stream.write(record)
            stream.flush()
            os.fsync(stream.fileno())

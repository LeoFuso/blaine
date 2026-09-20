"""Exact immutable artifacts; no Task lifecycle or semantic memory lives here."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from runtime.kernel.contracts import encode, identifier


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def put(self, task_id: str, content: bytes) -> str:
        identifier(task_id)
        digest = hashlib.sha256(content).hexdigest()
        directory = self.root / task_id
        directory.mkdir(mode=0o700, exist_ok=True)
        if directory.is_symlink():
            raise ValueError("Artifact directory cannot be a symlink")
        target = directory / digest
        # Publish complete bytes atomically, never expose a partially written object.
        fd, temporary = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
            directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            os.unlink(temporary)
        ref = f"artifact://{task_id}/sha256:{digest}"
        if self.read(task_id, ref) != content:
            raise ValueError("Artifact collision or corruption")
        return ref

    def read(self, task_id: str, ref: str) -> bytes:
        identifier(task_id)
        if not isinstance(ref, str):
            raise ValueError("Invalid artifact reference")
        match = re.fullmatch(r"artifact://([A-Za-z0-9_-]{1,80})/sha256:([0-9a-f]{64})", ref)
        if not match or match[1] != task_id:
            raise ValueError("Invalid or cross-Task artifact reference")
        path = self.root / task_id / match[2]
        if path.parent.is_symlink() or path.is_symlink():
            raise ValueError("Artifact path cannot be a symlink")
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != match[2]:
            raise ValueError("Artifact digest mismatch")
        return data

    def put_json(self, task_id: str, value: object) -> str:
        return self.put(task_id, encode(value))

    def read_json(self, task_id: str, ref: str) -> dict:
        return json.loads(self.read(task_id, ref))

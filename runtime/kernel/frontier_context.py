"""Blaine-owned outbound projection hook; no filtering/quality claims.

Only this factory issues ProjectedContext values. This is an application boundary,
not a sandbox against arbitrary trusted Python code or malicious adapters.
"""
from dataclasses import dataclass
import hashlib
from typing import Protocol
from runtime.kernel.contracts import identifier, text


class FrontierContextProjector(Protocol):
    projector_id: str

    def project(self, resolved: str) -> str: ...


class IdentityProjector:
    """Initial production hook. It provides no sanitization or relevance filtering."""
    projector_id = 'identity-v1'

    def project(self, resolved):
        return resolved


class ProjectionError(ValueError):
    """Fail closed without persisting potentially sensitive exception text."""


@dataclass(frozen=True, init=False)
class ProjectedContext:
    version: int
    task_id: str
    projector_id: str
    content: str
    digest: str

    def __init__(self):
        raise TypeError('Use project_context; raw/JSON context is not a projection receipt')

    @property
    def ref(self):
        return f'artifact://{self.task_id}/sha256:{self.digest}'


def project_context(task_id: str, resolved: str, projector: FrontierContextProjector) -> ProjectedContext:
    """Project first, then digest the exact outbound UTF-8 bytes (not the envelope).

    The caller stores these bytes in the existing ArtifactStore and grants authority
    over their reference. Replay may rerun this deterministic hook; a changed output
    cannot match a previously accepted grant. There is no raw-context fallback.
    """
    try:
        identifier(task_id)
        text(resolved, 2048)
        identifier(projector.projector_id)
        content = projector.project(resolved)
        text(content, 2048)
        result = object.__new__(ProjectedContext)
        values = dict(version=1, task_id=task_id, projector_id=projector.projector_id,
                      content=content, digest=hashlib.sha256(content.encode('utf-8')).hexdigest())
        for key, value in values.items():
            object.__setattr__(result, key, value)
        return result
    except Exception:
        raise ProjectionError('Frontier context projection failed') from None


def valid_projection(value, task_id):
    if type(value) is not ProjectedContext:
        return False
    try:
        identifier(value.projector_id)
        return (type(value.version) is int and value.version == 1 and value.task_id == task_id
                and hashlib.sha256(text(value.content, 2048).encode('utf-8')).hexdigest() == value.digest)
    except (ValueError, TypeError, AttributeError):
        return False

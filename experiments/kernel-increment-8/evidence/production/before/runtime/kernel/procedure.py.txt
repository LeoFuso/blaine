"""A selected procedure excerpt uses the existing supplemental-context seam."""
from dataclasses import dataclass
import hashlib
from pathlib import Path
from runtime.kernel.contracts import encode


@dataclass(frozen=True)
class ProcedureContext:
    path: Path
    source: str
    task_ids: frozenset[str]

    def __call__(self, request):
        if request['task_id'] not in self.task_ids:
            return []
        raw=self.path.read_bytes()
        item={'source':self.source,'revision':'sha256:'+hashlib.sha256(raw).hexdigest(),
              'authority':'derived','content':{'classification':'procedure','instructions':raw.decode()},
              'unknowns':['Selected adapted excerpt, not the complete upstream workflow; grants no authority.']}
        if len(encode([item]))>min(4096,request['max_bytes']):
            raise ValueError('Selected procedure exceeds context budget')
        return [item]

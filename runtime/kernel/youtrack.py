"""One read-only Card capability. Connector transport and target scope are injected."""
from dataclasses import dataclass
from collections.abc import Callable
from runtime.kernel.contracts import encode, text


@dataclass(frozen=True)
class YouTrackRead:
    read: Callable[[str], dict]
    allowed_issues: frozenset[str]

    def __call__(self, issue_id):
        text(issue_id, 80)
        if issue_id not in self.allowed_issues:
            raise ValueError('Card read outside deployment-approved scope')
        raw = self.read(issue_id)
        if not isinstance(raw, dict) or len(encode(raw)) > 65536 or raw.get('id') != issue_id:
            raise ValueError('Invalid or misaddressed Card response')
        if not isinstance(raw.get('summary'), str) or not isinstance(raw.get('url'), str):
            raise ValueError('Card identity/source missing')
        return {'issue_id': issue_id, 'summary': raw['summary'][:512],
                'url': raw['url'][:512], 'description': str(raw.get('description') or '')[:1600],
                'authority': 'human_coordination',
                'unknowns': ['Bounded snapshot; Card status is not Task lifecycle or completion evidence.']}

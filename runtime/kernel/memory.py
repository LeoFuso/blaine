"""Optional, bounded MIRIX semantic retrieval; no writes or Task authority."""
from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from urllib.parse import urlencode, urlsplit
import urllib.request

from runtime.kernel.contracts import encode
from runtime.kernel.model import NoRedirect, strict_json


@dataclass(frozen=True)
class MirixContext:
    client_id: str
    user_id: str | None = None
    endpoint: str = 'http://127.0.0.1:8531'
    filter_tags: dict | None = None
    transport: Callable[[dict], dict] | None = None
    audit: Callable[[dict], None] | None = None

    def __post_init__(self):
        address = urlsplit(self.endpoint)
        if (address.scheme != 'http' or address.hostname not in ('127.0.0.1', '::1') or
                address.username or address.password or address.query or address.fragment):
            raise ValueError('MIRIX must use a configured loopback endpoint')
        if not isinstance(self.client_id, str) or not self.client_id:
            raise ValueError('An existing MIRIX client identity is required')

    def request(self, query):
        request = urllib.request.Request(self.endpoint.rstrip('/') + '/memory/search?' + urlencode(query),
                                         headers={'x-client-id': self.client_id})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        with opener.open(request, timeout=20) as response:
            data = response.read(32769)
            if len(data) > 32768:
                raise ValueError('MIRIX response exceeds retrieval bound')
            return strict_json(data)

    def __call__(self, request):
        query = {'query': request['objective'][:512], 'memory_type': 'semantic',
                 'search_field': 'details', 'search_method': 'embedding', 'limit': 2,
                 'similarity_threshold': 0.5, 'include_core_memory': 'false'}
        if self.user_id:
            query['user_id'] = self.user_id
        if self.filter_tags:
            query['filter_tags'] = encode(self.filter_tags).decode()
        result = (self.transport or self.request)(query)
        if (not isinstance(result, dict) or result.get('success') is not True or
                not isinstance(result.get('results'), list) or len(result['results']) > 2 or
                result.get('search_method') != 'embedding'):
            raise ValueError('Invalid MIRIX semantic search response')
        items = []
        for row in result['results']:
            if (row.get('memory_type') != 'semantic' or not isinstance(row.get('id'), str) or
                    not row['id'] or not isinstance(row.get('details'), str) or
                    not isinstance(row.get('summary'), str)):
                raise ValueError('MIRIX semantic identity/content required')
            selected = {'classification': 'semantic_memory', 'memory_id': row['id'],
                        'summary': row['summary'][:512], 'details': row['details'][:1024],
                        'reported_source': str(row.get('source') or 'unknown')[:256]}
            item = {'source': self.endpoint.rstrip('/') + '/memory/semantic/' + row['id'],
                    'revision': 'sha256:' + hashlib.sha256(encode(row)).hexdigest(),
                    'authority': 'derived', 'content': selected,
                    'unknowns': ['Retrieved memory is unverified; current Task and exact evidence take precedence.']}
            if len(row['details']) > 1024 or len(row['summary']) > 512:
                item['unknowns'].append('Memory text truncated to context budget.')
            if len(encode(items + [item])) > min(request['max_bytes'], 4096):
                break
            items.append(item)
        if self.audit:
            self.audit({'task_id': request['task_id'], 'endpoint': self.endpoint,
                        'client_id': self.client_id, 'query': query, 'response': result,
                        'context': items, 'context_bytes': len(encode(items))})
        return items

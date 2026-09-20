"""Optional, bounded navigation over a derived Graphify snapshot. Source remains authority."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from runtime.kernel.contracts import MAX_CONTENT, encode


@dataclass(frozen=True)
class ProjectKnowledgeContext:
    source_root: Path
    snapshot: Path | None
    # Exact source-byte digests captured alongside indexing; a HEAD stamp is insufficient.
    indexed_sources: Mapping[str, str]
    audit: Callable[[dict], None] | None = None

    def __call__(self, request):
        trace = {'query': request['objective'], 'selected': [], 'excluded': []}
        if self.snapshot is None:
            if self.audit: self.audit({**trace, 'status': 'absent'})
            return []
        with self.snapshot.open('rb') as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError('Project index exceeds bounded snapshot size')
        graph = json.loads(raw)
        nodes = graph.get('nodes')
        if not isinstance(nodes, list) or len(nodes) > 10000:
            raise ValueError('Expected bounded Graphify nodes')
        digest = hashlib.sha256(raw).hexdigest()
        trace['index_sha256'] = digest
        words = set(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', request['objective'].lower()))
        candidates = [n for n in nodes if isinstance(n, dict) and isinstance(n.get('label'), str)
            and words.intersection(re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*', n['label'].lower()))]
        candidates.sort(key=lambda n: str(n.get('id', '')))
        root = self.source_root.resolve()
        result = []
        for node in candidates[:8]:
            if len(result) == 3: break
            relative = node.get('source_file')
            if not isinstance(relative, str) or Path(relative).is_absolute():
                raise ValueError('Relative source provenance is required')
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError('Source escapes selected project')
            expected = self.indexed_sources.get(relative)
            row = {'id': node.get('id'), 'source_file': relative, 'indexed_source_sha256': expected}
            if expected is None:
                trace['excluded'].append({**row, 'reason': 'source revision unknown'})
                continue
            if not re.fullmatch('[a-f0-9]{64}', expected):
                raise ValueError('Expected exact indexed source SHA-256')
            try:
                with path.open('rb') as stream: source = stream.read(65537)
            except FileNotFoundError:
                trace['excluded'].append({**row, 'reason': 'source no longer exists'})
                continue
            if len(source) > 65536: raise ValueError('Source exceeds bounded verification read')
            current = hashlib.sha256(source).hexdigest()
            row['current_source_sha256'] = current
            if current != expected:
                trace['excluded'].append({**row, 'reason': 'source digest mismatch'})
                continue
            # Whitelist navigation metadata, not arbitrary summaries, state, confidence
            # claims, learned answers, or possibly incomplete graph relationships.
            content = {'classification': 'project_knowledge', 'node_id': node.get('id'),
                'label': node['label'], 'source_file': relative, 'source_location': node.get('source_location'),
                'source_sha256': current, 'freshness': 'source_digest_matches',
                'derivation': 'Graphify navigation; reported origin: ' + str(node.get('_origin', 'unknown'))[:80]}
            item = {'source': 'graphify:sha256:' + digest, 'revision': digest,
                'authority': 'derived', 'content': content,
                'unknowns': ['Matching source bytes do not certify extractor claims. Recheck consequential claims against current source.']}
            if len(encode(item)) > 1536 or len(encode(result + [item])) > min(request['max_bytes'], MAX_CONTENT):
                trace['excluded'].append({**row, 'reason': 'context budget'})
                continue
            result.append(item);trace['selected'].append(row)
        if self.audit: self.audit({**trace, 'status': 'retrieved', 'context_bytes': len(encode(result)), 'context': result})
        return result

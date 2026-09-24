"""One frozen III.8R selection policy; no oracle reads or model calls."""
import argparse
from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
OLD = HERE.with_name('track-iii-008')
sys.path.insert(0, str(OLD))
from source import declarations, relation_valid, wire
from discover import Discovery


def read(path):
    return json.loads(path.read_text())


def family(row):
    return hashlib.sha256(re.sub(r'\d+', '#', row['text']).encode()).hexdigest()


def recover(variant='correct'):
    policy = read(HERE / 'policy.json')
    name = {'correct': 'results', 'fallback': 'stale-safe'}.get(variant, variant)
    original = read(OLD / f'evidence/{name}.json')
    engine = Discovery()
    queries = {q['id']: q for q in read(OLD / 'queries.json')}
    results = []
    for old in original:
        if old['mode'] != 'COMBINED':
            continue
        rev = old['revision']
        q = queries[old['query']]
        current = declarations(rev)
        idx_rev = 'A' if variant in ('stale-safe', 'freshness', 'fallback') and rev == 'B' else rev
        index = engine.indexes[idx_rev]
        scope = engine.scope_revision(current, engine.binding)
        derived_scope = engine.scope_revision(index['rows'], engine.binding)
        indexed = {t: r for t, r in index['rows'].items()
                   if variant == 'isolation' or engine.permitted(t, engine.binding)}
        structural, edges = engine.structural(q, index, indexed)
        assert structural == old['raw']['STRUCTURAL']
        contributions = []
        for mechanism, hits in old['raw'].items():
            for rank, hit in enumerate(hits, 1):
                target = hit['target']
                row = (current if mechanism == 'LEXICAL' else index['rows']).get(target)
                reasons = []
                if variant != 'isolation' and not engine.permitted(target, engine.binding):
                    reasons.append('FORBIDDEN')
                if not isinstance(row, dict):
                    reasons.append('MALFORMED')
                elif variant != 'freshness':
                    live = current.get(target)
                    if not live or any(row[k] != live[k] for k in ('source_hash', 'text', 'line')):
                        reasons.append('STALE_SOURCE')
                    if mechanism != 'LEXICAL' and derived_scope != scope:
                        reasons.append('STALE_REVISION')
                    if mechanism == 'STRUCTURAL' and any(
                            not relation_valid(e, current) for e in edges
                            if target in (e['source'], e['target'])):
                        reasons.append('STALE_RELATION')
                contributions.append({'target': target, 'mechanism': mechanism,
                                      'original_rank': rank, 'reasons': reasons,
                                      'record': row})
        # The fallback mutant intentionally admits invalid contributions to competition.
        eligible = [c for c in contributions if not c['reasons'] or variant == 'fallback']
        families_by_mechanism = {}
        targets = {}
        for c in eligible:
            row = c['record']
            f = family(row)
            families = families_by_mechanism.setdefault(c['mechanism'], [])
            if f not in families:
                families.append(f)
            rank = families.index(f) + 1
            c['family_rank'] = rank
            item = targets.setdefault(c['target'], {'target': c['target'], 'record': row,
                                                  'family': f, 'ranks': {}, 'score': Fraction(0)})
            item['ranks'][c['mechanism']] = rank
            item['score'] += Fraction(1, policy['rrf_k'] + rank)
        def confidence(item):
            if 'LEXICAL' in item['ranks'] and item['record']['symbol'].casefold() == q['text'].casefold():
                return 0
            return 1 if 'STRUCTURAL' in item['ranks'] else 2
        fused = sorted(targets.values(), key=lambda t: (confidence(t), -t['score'],
                                                       min(t['ranks'].values()), t['target']))
        # Diversity is a round-robin over source families in fused order.
        pending = list(fused)
        order = []
        while pending:
            seen = set()
            deferred = []
            for item in pending:
                if item['family'] in seen and confidence(item) != 0:
                    deferred.append(item)
                else:
                    order.append(item)
                    seen.add(item['family'])
            pending = deferred
        codes = {'LEXICAL': 'L', 'SEMANTIC': 'S', 'STRUCTURAL': 'G'}
        def render(selected, partial):
            ids = {item['target']: i for i, item in enumerate(selected)}
            relations = [[ids[e['source']], e['relation'], ids[e['target']]] for e in edges
                         if e['source'] in ids and e['target'] in ids
                         and ('STRUCTURAL' in targets[e['source']]['ranks'] or
                              'STRUCTURAL' in targets[e['target']]['ranks'])]
            entries = [{'target': t['target'], 'line': t['record']['line'],
                        'excerpt': t['record']['text'][:policy['excerpt_characters']],
                        'via': ''.join(codes[m] for m in sorted(t['ranks']))} for t in selected]
            return {'revision': scope, 'derived_state': 'CURRENT' if derived_scope == scope or variant == 'freshness' else 'STALE_EXCLUDED',
                    'entries': entries, 'relations': relations,
                    'diagnostic': {'status': 'SUCCESS' if selected else 'EMPTY',
                                   'selected': len(selected), 'partial': partial}}
        selected = []
        omitted = []
        for item in order:
            # Account for the complete envelope for both possible final partial states.
            trial = selected + [item]
            if max(len(wire(render(trial, p))) for p in (True, False)) <= policy['packet_bytes']:
                selected = trial
            else:
                omitted.append(item['target'])
        provisional = [t['target'] for t in selected]
        late_dropped = []
        if variant == 'fallback':
            invalid = {c['target'] for c in contributions if c['reasons']}
            late_dropped = [t['target'] for t in selected if t['target'] in invalid]
            selected = [t for t in selected if t['target'] not in invalid]
        output = render(selected, bool(omitted or late_dropped))
        audit = []
        for rank, item in enumerate(fused, 1):
            audit.append({'target': item['target'], 'identity': [scope, item['record']['file'], item['record']['symbol'], item['record']['line']],
                          'family': item['family'], 'ranks': item['ranks'],
                          'rrf': str(item['score']), 'fused_rank': rank,
                          'selection_rank': next(i for i, t in enumerate(order, 1) if t['target'] == item['target']),
                          'confidence': confidence(item), 'selected': item['target'] in {t['target'] for t in selected}})
        results.append({'revision': rev, 'query': q['id'], 'group': q['group'], 'variant': variant,
                        'input_evidence': f'../track-iii-008/evidence/{name}.json',
                        'raw': old['raw'], 'derived_revision': derived_scope,
                        'contributions': contributions, 'deduplicated': audit,
                        'exact_reservation': [t['target'] for t in fused if confidence(t) == 0],
                        'provisional_selected': provisional, 'late_dropped': late_dropped,
                        'omitted': omitted, 'output': output,
                        'complete_bytes': len(wire(output))})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--variant', choices=['correct', 'stale-safe', 'freshness', 'isolation', 'fallback'], default='correct')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(recover(args.variant), indent=2, sort_keys=True) + '\n')

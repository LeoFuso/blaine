"""Independent retained-evidence checker: source AST, original oracles, literal leaks."""
import argparse
import ast
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
OLD = HERE.with_name('track-iii-008')


def read(p):
    return json.loads(p.read_text())


def wire(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def source(revision):
    files = {}
    rows = {}
    for path in sorted((OLD / 'workspace' / revision).rglob('*.py')):
        rel = str(path.relative_to(OLD / 'workspace' / revision))
        files[rel] = sha(path)
        text = path.read_text()
        tree = ast.parse(text)
        imports = {a.name for n in tree.body if isinstance(n, ast.ImportFrom) for a in n.names}
        for n in tree.body:
            name = n.name if isinstance(n, (ast.ClassDef, ast.FunctionDef)) else n.targets[0].id if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) else None
            if name:
                rows[rel + '::' + name] = {'line': n.lineno, 'text': '\n'.join(text.splitlines()[n.lineno-1:n.end_lineno]),
                                         'symbol': name, 'hash': files[rel], 'imports': imports,
                                         'calls': {ast.unparse(c.func) for c in ast.walk(n) if isinstance(c, ast.Call)},
                                         'inherits': {ast.unparse(b) for b in n.bases} if isinstance(n, ast.ClassDef) else set()}
    visible = {p: h for p, h in files.items() if p.startswith('personal/')}
    return rows, 'sha256:' + hashlib.sha256(wire(visible)).hexdigest()


def evaluate(data, control=False):
    frozen = read(HERE / 'frozen-assets.json')
    original = read(OLD / 'evidence/results.json')
    queries = read(OLD / 'queries.json')
    oracles = read(OLD / 'oracles.json')
    security = read(OLD / 'security.json')
    policy = read(HERE / 'policy.json')
    checks = []
    def check(name, good):
        checks.append({'check': name, 'pass': bool(good)})
    check('all-iii8-assets-unchanged', all(sha(OLD / p) == h for p, h in frozen['all_iii8_files_sha256'].items()))
    check('policy-frozen', sha(HERE / 'policy.json') == frozen['policy_sha256'] and frozen['prior_recovery_comparisons'] == 0)
    registration = read(HERE / 'evidence/preregistration.json')
    check('implementation-frozen', all(sha(HERE / p) == h for p, h in registration['files'].items()))
    check('original-thresholds', policy['packet_bytes'] == 2048 and policy['threshold_unique_gain_each_revision'] == 2)
    check('original-query-taxonomy', len(queries) == 12 and all(sum(q['group'] == g for q in queries) == 4 for g in ('LEXICAL', 'SEMANTIC', 'STRUCTURAL')))
    check('both-revisions-exactly', len(data) == 24 and {(r['revision'], r['query']) for r in data} == {(v, q['id']) for v in ('A', 'B') for q in queries})
    stale = []
    forbidden = []
    metrics = []
    canonical = []
    fallback = []
    for row in data:
        rev, qid = row['revision'], row['query']
        key = rev + '/' + qid
        q = next(q for q in queries if q['id'] == qid)
        live, scope = source(rev)
        packet = row['output']
        entries = packet['entries']
        ids = {e['target'] for e in entries}
        old = next(r for r in original if r['revision'] == rev and r['query'] == qid and r['mode'] == 'LEXICAL')
        broad_original = next(r for r in original if r['revision'] == rev and r['query'] == qid and r['mode'] == 'COMBINED')
        baseline = {e['target'] for e in old['output']['packet']['entries']}
        expected = set(oracles[rev][qid]['required'])
        allowed = set(oracles[rev][qid]['acceptable'])
        check('budget/' + key, len(wire(packet)) <= 2048 and row['complete_bytes'] == len(wire(packet)))
        check('revision/' + key, packet['revision'] == scope)
        check('dedup/' + key, len(ids) == len(entries) and len(row['deduplicated']) == len({x['target'] for x in row['deduplicated']}))
        source_results = read((HERE / row['input_evidence']).resolve())
        src = next(r for r in source_results if r['revision'] == rev and r['query'] == qid and r['mode'] == 'COMBINED')
        check('raw-lists-unchanged/' + key, row['raw'] == src['raw'])
        if row['variant'] == 'correct':
            check('original-candidate-set/' + key, row['raw'] == broad_original['raw'])
        for entry in entries:
            target = entry['target']
            actual = live.get(target)
            bad = not actual or actual['line'] != entry['line'] or actual['text'][:80] != entry['excerpt']
            if ('S' in entry['via'] or 'G' in entry['via']) and row['derived_revision'] != scope:
                bad = True
            if bad:
                stale.append({'case': key, 'target': target})
            if not target.startswith('personal/'):
                forbidden.append({'case': key, 'target': target})
            audit = next((a for a in row['deduplicated'] if a['target'] == target), None)
            check('provenance/' + key + '/' + target, audit is not None and entry['via'] == ''.join({'LEXICAL':'L','SEMANTIC':'S','STRUCTURAL':'G'}[m] for m in sorted(audit['ranks'])))
        for a, relation, b in packet['relations']:
            source_row, target_row = live.get(entries[a]['target']), live.get(entries[b]['target'])
            valid = source_row and target_row and target_row['symbol'] in source_row[relation]
            if not valid:
                stale.append({'case': key, 'edge': [a, relation, b]})
        serialized = wire(packet).decode()
        if any(lit in serialized for lit in security['forbidden_literals']):
            forbidden.append({'case': key, 'literal_scan': True})
        if row['variant'] in ('correct', 'stale-safe'):
            valid_targets = {c['target'] for c in row['contributions'] if not c['reasons']}
            check('invalid-eliminated-before-fusion/' + key, {a['target'] for a in row['deduplicated']} == valid_targets)
            for c in row['contributions']:
                actual = live.get(c['target'])
                supported = bool(actual and c['record']['source_hash'] == actual['hash'] and c['record']['text'] == actual['text'] and c['record']['line'] == actual['line'] and c['target'].startswith('personal/'))
                if c['mechanism'] != 'LEXICAL':
                    supported = supported and row['derived_revision'] == scope
                check('independent-validation/' + key + '/' + c['mechanism'] + '/' + c['target'], bool(c['reasons']) == (not supported))
            # Reconstruct distinct-family ranks from valid ordered contributions.
            family_ranks = {}
            mechanism_families = {}
            for c in row['contributions']:
                if c['reasons']:
                    continue
                f = hashlib.sha256(re.sub(r'\d+', '#', c['record']['text']).encode()).hexdigest()
                seen = mechanism_families.setdefault(c['mechanism'], [])
                if f not in seen:
                    seen.append(f)
                family_ranks.setdefault(c['target'], {})[c['mechanism']] = seen.index(f) + 1
            for a in row['deduplicated']:
                check('rank-fusion/' + key + '/' + a['target'], a['ranks'] == family_ranks[a['target']] and Fraction(a['rrf']) == sum((Fraction(1, 60 + r) for r in a['ranks'].values()), Fraction(0)))
            check('exact-reservation/' + key, set(row['exact_reservation']) <= ids)
        hit = ids & expected
        base_hit = baseline & expected
        if not control:
            check('required-coverage/' + key, hit == expected)
        if q['group'] == 'LEXICAL':
            check('exact-retention/' + key, base_hit <= ids)
        metrics.append({'revision': rev, 'query': qid, 'group': q['group'], 'baseline_hits': sorted(base_hit), 'recovery_hits': sorted(hit), 'required': sorted(expected), 'acceptable_hits': sorted(ids & allowed), 'misses': sorted(expected-ids), 'gains': sorted(hit-base_hit), 'bytes': len(wire(packet))})
        if qid == 'S1':
            for target in sorted(expected):
                a = next((a for a in row['deduplicated'] if a['target'] == target), None)
                e = next((e for e in entries if e['target'] == target), None)
                canonical.append({'revision': rev, 'target': target, 'original_broad_rank': broad_original['ordered'].index(target)+1 if target in broad_original['ordered'] else None,
                                  'original_mechanism_ranks': {m: next((i for i,h in enumerate(v,1) if h['target'] == target),None) for m,v in broad_original['raw'].items()},
                                  'validation': [{'mechanism':c['mechanism'],'reasons':c['reasons']} for c in row['contributions'] if c['target']==target],
                                  'canonical_identity': a['identity'] if a else None,'fused_rank':a['fused_rank'] if a else None,'selection_rank':a['selection_rank'] if a else None,
                                  'entry_bytes':len(wire(e)) if e else None,'included':target in ids})
        if rev == 'B' and q['group'] == 'LEXICAL' and row['variant'] in ('stale-safe','fallback'):
            fallback.append({'query':qid,'required_fresh':sorted(base_hit),'emitted':sorted(ids & base_hit),'stale_contributions_removed':sum(bool(c['reasons']) for c in row['contributions']),'late_dropped':row['late_dropped']})
    aggregate = []
    for rev in ('A','B'):
        groups = {}
        for group in ('LEXICAL','SEMANTIC','STRUCTURAL'):
            selected = [m for m in metrics if m['revision']==rev and m['group']==group]
            groups[group] = {'baseline':sum(len(m['baseline_hits']) for m in selected),'recovery':sum(len(m['recovery_hits']) for m in selected),'required':sum(len(m['required']) for m in selected),'unique_gains':sorted({t for m in selected for t in m['gains']})}
        gains = sorted(set(groups['SEMANTIC']['unique_gains']) | set(groups['STRUCTURAL']['unique_gains']))
        aggregate.append({'revision':rev,'groups':groups,'unique_nonlexical_gain':len(gains),'gained_targets':gains})
        if not control:
            check('gain-threshold/'+rev,len(gains)>=2)
            check('canonical-inclusion/'+rev,all(d['included'] for d in canonical if d['revision']==rev))
    check('no-stale-emission',not stale)
    check('no-forbidden-emission',not forbidden)
    return {'status':'PASS' if all(c['pass'] for c in checks) else 'FAIL','checks':checks,'failed':[c['check'] for c in checks if not c['pass']],
            'metrics':metrics,'aggregate':aggregate,'canonical':canonical,'fallback':fallback,'stale':stale,'forbidden':forbidden,
            'max_complete_bytes':max(m['bytes'] for m in metrics)}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('input')
    p.add_argument('--control',action='store_true')
    p.add_argument('--output',required=True)
    args = p.parse_args()
    result = evaluate(read(Path(args.input)), args.control)
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:result[k] for k in ('status','failed','aggregate','max_complete_bytes')}))
    raise SystemExit(int(result['status']!='PASS'))

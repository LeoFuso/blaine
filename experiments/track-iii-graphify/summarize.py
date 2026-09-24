"""Summarize independently checked evidence, keeping operation and wall costs separate."""
from collections import Counter
import hashlib
from source import HERE,load,save


def main():
    v=load(HERE/'evidence/verification.json');rows=load(HERE/'evidence/results.json')
    validations=load(HERE/'evidence/validation.json');repos=load(HERE/'repositories.json');costs={};confidence={}
    for repo in repos:
        costs[repo]={rev:load(HERE/'evidence/indexes'/repo/rev/'cost.json') for rev in ['A','B']}
        costs[repo]['collection_wall_seconds']={rev:load(HERE/'evidence/indexes'/repo/rev/'invocation.json')['wall_seconds'] for rev in ['A','B']}
        costs[repo]['validation_setup']={k:validations[repo][k] for k in ['construction_seconds','source_validation']}
        confidence[repo]={'B_raw':costs[repo]['B']['confidence'],'validation':validations[repo]['counters']}
        for label in ['EXTRACTED','INFERRED']:
            selected=[(r,a) for r in rows if r['repo']==repo and r['condition']=='B' for a in r['selected'] if any(label in e['confidence'] for e in a['steps'])]
            confidence[repo][label+'_selected']={'answer_occurrences':len(selected),'query_targets':[[r['query'],a['target']] for r,a in selected],
                'false_positives':sum(len(m['false_positives']) for m in v['metrics'] if m['repo']==repo and m['condition']=='B'),
                'note':'Answer may use both confidence classes. Unsupported/unresolved validation counts are conservative exclusions, not all proven upstream false positives.'}
    s=dict(status=v['status'],classification='ADAPT / ON-DEMAND',query_manifest_sha256=hashlib.sha256((HERE/'queries.json').read_bytes()).hexdigest(),
           gates=dict(additional_unique_targets={c:len(v['unique_gains']['ALL'][c]) for c in ['B','C']},direct_losses=v['direct_losses'],
             trap_regressions=v['trap_regressions'],exploration_reductions=v['exploration_reductions'],max_packet_bytes=v['max_packet_bytes'],
             stale_emitted=v['stale_emitted'],forbidden_emitted=v['forbidden_emitted']),
           repository_pins={repo:{r:repos[repo][r]['commit'] for r in ['A','B']} for repo in repos},graphify=load(HERE/'graphify.json'),
           totals=v['totals'],confidence=confidence,costs=costs,freshness=v['freshness'],mutations=load(HERE/'evidence/mutation-controls.json'),
           reproduction=load(HERE/'evidence/reproduction.json')['status'],checker_assertions=len(v['checks']),
           interpretation='Useful bounded structural neighborhoods; corpus-dependent gain, overload/call limitations, nonzero source-validation cost, no local wall-time improvement, no production adoption.',
           optional_isolation_control='Protected candidate reached internal mutant candidates but did not fit packet; no emitted leak, control inconclusive. Not a frozen mandatory gate.',
           model_calls=0,ranking_or_oracle_tuning=False,production_changes=False)
    save(HERE/'evidence/summary.json',s)
    exports=[dict(query=r['query'],condition=r['condition'],packet=r['packet']) for r in rows]
    save(HERE/'evidence/exports.json',exports)
    print(s['status'],s['gates'])


if __name__=='__main__':main()

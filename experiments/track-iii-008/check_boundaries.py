"""Supplementary III.8 binding/metadata controls; no retrieval-quality tuning."""
from copy import deepcopy
from source import HERE,load,save
from discover import Discovery


def main():
    checks=[]
    def check(name,expected,actual):checks.append({'case':name,'expected':expected,'actual':actual,'status':'PASS' if expected==actual else 'FAIL'})
    original=Discovery();queries=load('queries.json')
    for rev in ('A','B'):
        for q in queries:
            d=Discovery();expected=d.query(d.binding,q,rev,'COMBINED')['output']
            for idx in d.indexes.values():
                idx['rows']={k:v for k,v in idx['rows'].items() if not k.startswith('employer-x/')}
                idx['edges']=[e for e in idx['edges'] if not any(e[k].startswith('employer-x/') for k in ('source','target'))]
            check('foreign-existence-not-observable/'+rev+'/'+q['id'],expected,d.query(d.binding,q,rev,'COMBINED')['output'])
    q=queries[0]
    check('forged-binding',{'packet':{'status':'DENIED','entries':[]},'diagnostic':{'status':'DENIED'}},original.query(object(),q,'A','COMBINED'))
    check('foreign-context-binding',{'packet':{'status':'DENIED','entries':[]},'diagnostic':{'status':'DENIED'}},original.query(original.tree.bind('employer-x'),q,'A','COMBINED'))
    d=Discovery();d.policy=None
    check('policy-unavailable',{'packet':{'status':'UNAVAILABLE','entries':[]},'diagnostic':{'status':'UNAVAILABLE'}},d.query(d.binding,q,'A','COMBINED'))
    d=Discovery();d.policy={}
    check('policy-malformed',{'packet':{'status':'DENIED','entries':[]},'diagnostic':{'status':'DENIED'}},d.query(d.binding,q,'A','COMBINED'))
    r={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks}
    save(HERE/'evidence/boundaries.json',r)
    return int(r['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())

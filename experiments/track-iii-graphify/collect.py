"""Real pinned Java extraction. No query evaluation, model or network."""
import argparse
from collections import Counter
import gzip
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tarfile
import time
from source import HERE,ROOTS,load,save,wire,inventory


def gz(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(gzip.compress(wire(value).encode(),mtime=0))


def child(repo,root,cache,output):
    cfg=load(HERE/'graphify.json'); sys.path.insert(0,cfg['checkout'])
    from graphify.extract import extract
    from graphify.build import build_from_json
    root=Path(root);output=Path(output);cache=Path(cache)
    paths=sorted((root/ROOTS[repo]).rglob('*.java'))
    start=time.perf_counter();raw=extract(paths,root=root,cache_root=cache,parallel=False)
    extraction=time.perf_counter()-start
    start=time.perf_counter();graph=build_from_json(raw,directed=True,root=root)
    build=time.perf_counter()-start
    gz(output/'raw.json.gz',raw)
    save(output/'cost.json',dict(java_files=len(paths),extraction_seconds=extraction,build_seconds=build,
         peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         raw_nodes=len(raw['nodes']),raw_edges=len(raw['edges']),graph_nodes=len(graph),graph_edges=graph.number_of_edges(),
         confidence=dict(Counter(e.get('confidence','ABSENT') for e in raw['edges'])),
         relations=dict(Counter(e.get('relation','ABSENT') for e in raw['edges'])),
         failed_sources=raw.get('failed_sources',[]),raw_json_bytes=len(wire(raw).encode()),
         compressed_graph_bytes=(output/'raw.json.gz').stat().st_size,
         parse_cache_bytes=sum(p.stat().st_size for p in cache.rglob('*') if p.is_file())))
    gz(output/'source.json.gz',inventory(root,repo))
    # Unmodified authoritative Java sources plus license, separate from indexes.
    from io import BytesIO
    buf=BytesIO()
    with tarfile.open(fileobj=buf,mode='w') as tf:
        licenses=[p for p in root.iterdir() if p.is_file() and p.name.lower().startswith(('license','licence','notice','copyright'))]
        for p in sorted(paths+licenses):
            data=p.read_bytes();info=tarfile.TarInfo(p.relative_to(root).as_posix())
            info.size=len(data);info.mtime=0;info.mode=0o644
            tf.addfile(info,BytesIO(data))
    (output/'source.tar.gz').write_bytes(gzip.compress(buf.getvalue(),mtime=0))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--child',nargs=4);args=ap.parse_args()
    if args.child:return child(*args.child)
    cfg=load(HERE/'graphify.json');repositories=load(HERE/'repositories.json')
    assert subprocess.check_output(['git','-C',cfg['checkout'],'rev-parse','HEAD'],text=True).strip()==cfg['commit']
    assert not subprocess.check_output(['git','-C',cfg['checkout'],'status','--porcelain'],text=True).strip()
    output=HERE/'evidence/indexes';output.mkdir(exist_ok=True)
    operations=[]
    for repo,r in repositories.items():
        work=Path('/tmp/blaine-iii-g')/(repo+'-extract')
        if not work.exists():
            subprocess.run(['git','-C',r['B']['path'],'worktree','add','--detach',str(work),r['A']['commit']],capture_output=True,check=True)
        cache=Path('/tmp/blaine-iii-g')/(repo+'-cache');cache.mkdir(exist_ok=True)
        for rev in ['A','B']:
            dest=output/repo/rev;dest.mkdir(parents=True,exist_ok=True)
            if (dest/'complete.json').exists():
                operations.append(load(dest/'complete.json'));continue
            subprocess.run(['git','-C',str(work),'checkout','--detach',r[rev]['commit']],capture_output=True,check=True)
            env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0',
                 'PYTHONPATH':str(HERE.parent/'graphify-carveout/offline'),
                 'GRAPHIFY_QUERY_LOG_DISABLE':'1','GRAPHIFY_MAX_WORKERS':'1','GRAPHIFY_OUT':str(cache/'graphify-out')}
            command=[cfg['python'],str(HERE/'collect.py'),'--child',repo,str(work),str(cache),str(dest)]
            start=time.perf_counter();p=subprocess.run(command,env=env,capture_output=True,text=True,timeout=300)
            elapsed=time.perf_counter()-start
            record=dict(repo=repo,revision=rev,commit=r[rev]['commit'],command=command,
                        exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr,wall_seconds=elapsed,
                        mode='initial full extraction' if rev=='A' else 'full graph rebuild with existing parse cache; not incremental graph update')
            save(dest/'invocation.json',record)
            if p.returncode:raise RuntimeError('Extraction failed; see invocation evidence')
            record['artifact_sha256']={n:hashlib.sha256((dest/n).read_bytes()).hexdigest() for n in ['raw.json.gz','source.json.gz','source.tar.gz','cost.json']}
            save(dest/'complete.json',record);operations.append(record)
            print(repo,rev,'complete',round(elapsed,3),'seconds',flush=True)
    save(HERE/'evidence/collection.json',operations)
    save(HERE/'evidence/packages.json',{d.metadata['Name']:d.version for d in importlib.metadata.distributions()})


if __name__=='__main__':main()

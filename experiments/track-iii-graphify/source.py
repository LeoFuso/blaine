"""Limited independent Java source facts for oracles/revalidation, not a graph service.

Tree-sitter syntax + explicit package/import resolution. No Graphify imports.
Only source-supported heritage/imports/local-or-statically-typed calls are facts;
reflection, dynamic dispatch, external dependencies and uncertain calls are unresolved.
"""
import hashlib
import json
from pathlib import Path
import re
import tree_sitter
import tree_sitter_java

HERE=Path(__file__).resolve().parent
ROOTS={'spring-kafka':'spring-kafka/src/main/java','jackson-databind':'src/main/java'}
PARSER=tree_sitter.Parser(tree_sitter.Language(tree_sitter_java.language()))
TYPES={'class_declaration','interface_declaration','enum_declaration','record_declaration','annotation_type_declaration'}

def wire(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x): return hashlib.sha256(wire(x).encode()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def save(p,x): Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
def walk(node):
    yield node
    for c in node.named_children: yield from walk(c)
def txt(n,b): return '' if n is None else b[n.start_byte:n.end_byte].decode()
def bare(s):
    s=re.sub(r'@[\w.]+(?:\([^)]*\))?','',s).strip()
    return re.sub(r'<.*>','',s).strip().removesuffix('[]')

def inventory(root,repo):
    root=Path(root); nodes={}; declarations={}; files={}; unresolved=[]
    for p in sorted((root/ROOTS[repo]).rglob('*.java')):
        b=p.read_bytes(); tree=PARSER.parse(b); path=p.relative_to(root).as_posix()
        pkg=re.search(rb'\bpackage\s+([\w.]+)\s*;',b)
        if not pkg: continue
        pkg=pkg.group(1).decode()
        imports=re.findall(rb'\bimport\s+(?:static\s+)?([\w.*]+)\s*;',b)
        files[path]={'sha256':hashlib.sha256(b).hexdigest(),'package':pkg,'imports':[x.decode() for x in imports]}
        def visit(n,owners):
            if n.type in TYPES:
                name=txt(n.child_by_field_name('name'),b); full=pkg+'.'+'.'.join(owners+[name])
                nodes[full]=dict(id=full,file=path,symbol='.'.join(owners+[name]),kind=n.type,
                                 line=n.start_point[0]+1,end=n.end_point[0]+1)
                declarations[full]=(n,b)
                owners=owners+[name]
            elif n.type in ('method_declaration','constructor_declaration') and owners:
                name=txt(n.child_by_field_name('name'),b)
                params=n.child_by_field_name('parameters')
                arity=sum(x.type in ('formal_parameter','spread_parameter','receiver_parameter') for x in params.named_children) if params else 0
                full=pkg+'.'+'.'.join(owners)+'#'+name+'/'+str(arity)
                # Overloads sharing arity are explicitly not resolvable by this limited validator.
                if full in nodes: nodes[full]['ambiguous']=True
                else:
                    nodes[full]=dict(id=full,file=path,symbol='.'.join(owners)+'#'+name+'/'+str(arity),kind=n.type,
                                     line=n.start_point[0]+1,end=n.end_point[0]+1)
                    declarations[full]=(n,b)
            for child in n.named_children: visit(child,owners)
        visit(tree.root_node,[])
        fid='file:'+path
        nodes[fid]=dict(id=fid,file=path,symbol='',kind='file',line=1,end=len(b.splitlines()))
    types={k for k,v in nodes.items() if v['kind'] in TYPES}
    def resolve(value,owner,path):
        value=bare(value)
        if value in types:return value
        f=files[path]; possible=[]
        for imp in f['imports']:
            if imp.endswith('.*'): possible.append(imp[:-1]+value)
            elif imp.rsplit('.',1)[-1]==value.split('.')[0]: possible.append(imp+value[len(value.split('.')[0]):])
        scope=owner.split('#')[0]
        while '.' in scope:
            possible.append(scope+'.'+value); scope=scope.rsplit('.',1)[0]
        possible.append(f['package']+'.'+value)
        found=list(dict.fromkeys(x for x in possible if x in types))
        return found[0] if len(found)==1 else None
    edges=[]
    def edge(a,z,rel,line):
        if z and a!=z: edges.append(dict(source=a,target=z,relation=rel,file=nodes[a]['file'],line=line))
    for key,(n,b) in declarations.items():
        if nodes[key]['kind'] not in TYPES: continue
        path=nodes[key]['file']
        for child in n.named_children:
            if child.type not in ('superclass','super_interfaces','extends_interfaces'):continue
            rel='implements' if child.type=='super_interfaces' else 'inherits'
            # Only outer parent type names, never generic type arguments.
            def parents(c):
                if c.type in ('type_identifier','scoped_type_identifier','generic_type'):
                    yield bare(txt(c,b)),c.start_point[0]+1
                else:
                    for cc in c.named_children: yield from parents(cc)
            for name,line in parents(child): edge(key,resolve(name,key,path),rel,line)
        for subkey,sub in nodes.items():
            if sub['file']==path and '#' in subkey and subkey.split('#')[0]==key:
                edge(key,subkey,'contains',sub['line'])
    for path,f in files.items():
        b=(root/path).read_bytes()
        for imp in f['imports']:
            if imp in types:
                line=next((i for i,l in enumerate(b.decode().splitlines(),1) if re.search(r'\bimport\s+'+re.escape(imp)+r'\s*;',l)),1)
                edge('file:'+path,imp,'imports',line)
    parents={k:[e['target'] for e in edges if e['source']==k and e['relation'] in ('inherits','implements')] for k in types}
    def method(owner,name,arity):
        todo=[owner];seen=set()
        while todo:
            now=todo.pop(0)
            if now in seen:continue
            seen.add(now); key=now+'#'+name+'/'+str(arity)
            if key in nodes and not nodes[key].get('ambiguous'):return key
            todo+=parents.get(now,[])
        return None
    for key,(n,b) in declarations.items():
        if '#' not in key or nodes[key].get('ambiguous'):continue
        owner=key.split('#')[0];path=nodes[key]['file'];owner_node=declarations[owner][0]
        variables={}
        for d in list(owner_node.named_children)+list(walk(n)):
            # Fields are nested inside class body.
            candidates=d.named_children if d.type=='class_body' else [d]
            for f in candidates:
                if f.type not in ('field_declaration','local_variable_declaration','formal_parameter'):continue
                t=resolve(txt(f.child_by_field_name('type'),b),owner,path)
                if not t:continue
                for v in f.named_children:
                    if v.type=='variable_declarator':variables[txt(v.child_by_field_name('name'),b)]=t
                if f.type=='formal_parameter':variables[txt(f.child_by_field_name('name'),b)]=t
        for call in walk(n):
            if call.type!='method_invocation':continue
            name=txt(call.child_by_field_name('name'),b);obj=txt(call.child_by_field_name('object'),b)
            args=call.child_by_field_name('arguments');arity=len(args.named_children) if args else 0
            target_owner=owner if obj in ('','this') else ((parents.get(owner) or [None])[0] if obj=='super' else variables.get(obj.removeprefix('this.')) or resolve(obj,owner,path))
            target=method(target_owner,name,arity) if target_owner else None
            if target: edge(key,target,'calls',call.start_point[0]+1)
            else: unresolved.append(dict(source=key,receiver=obj,name=name,line=call.start_point[0]+1))
    unique={wire(e):e for e in edges}
    return dict(nodes=nodes,edges=sorted(unique.values(),key=wire),files=files,unresolved_calls=unresolved)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('repo');p.add_argument('root');p.add_argument('output');a=p.parse_args()
    save(a.output,inventory(a.root,a.repo))

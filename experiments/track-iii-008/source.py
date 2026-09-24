"""Authoritative fixture declarations and relation verification, not a graph engine."""
import ast
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent

def wire(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
def digest(x):return hashlib.sha256(wire(x)).hexdigest()
def load(n):return json.loads((HERE/n).read_text())
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True,ensure_ascii=False)+'\n')

def declarations(rev):
    rows={};roots=HERE/'workspace'/rev
    for path in sorted(roots.rglob('*.py')):
        text=path.read_text();lines=text.splitlines();rel=str(path.relative_to(roots));module=ast.parse(text)
        imports=[n for n in module.body if isinstance(n,ast.ImportFrom)]
        for node in module.body:
            if isinstance(node,(ast.ClassDef,ast.FunctionDef)):name=node.name
            elif isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):name=node.targets[0].id
            else:continue
            snippet='\n'.join(lines[node.lineno-1:node.end_lineno]);key=rel+'::'+name
            rows[key]={'target':key,'file':rel,'symbol':name,'line':node.lineno,'end_line':node.end_lineno,'source_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'text':snippet,'imports':[alias.name for imp in imports for alias in imp.names],'bases':[ast.unparse(b) for b in node.bases] if isinstance(node,ast.ClassDef) else [],'calls':sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n,ast.Call)})}
    return rows


def relation_valid(edge,rows):
    a=rows.get(edge['source']);b=rows.get(edge['target'])
    if not a or not b:return False
    return b['symbol'] in a[{'inherits':'bases','calls':'calls','imports':'imports'}[edge['relation']]]

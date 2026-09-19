"""Small deterministic counterexamples for freshness, independent of Blaine source."""
import copy
import json
import os
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parents[1].parent / "graphify-upstream"
WORK = Path(tempfile.mkdtemp(prefix="freshness-", dir=HERE / "work"))
CORPUS = WORK / "corpus"
CORPUS.mkdir()
OUT = WORK / "graphify-out"
os.environ["GRAPHIFY_OUT"] = str(OUT)
os.environ["GRAPHIFY_MAX_WORKERS"] = "1"
sys.path.insert(0, str(UPSTREAM))
os.chdir(CORPUS)

from graphify.extract import extract
from graphify.build import build_from_json
from graphify.export import to_json
from graphify.watch import _rebuild_code
from graphify.serve import _load_graph

results = {}
doc = CORPUS / "notes.md"
doc.write_text('---\nreview_status: draft\n---\n# Project\n')
first = extract([doc], root=CORPUS, cache_root=WORK, parallel=False)
doc.write_text('---\nreview_status: accepted\n---\n# Project\n')
warm = extract([doc], root=CORPUS, cache_root=WORK, parallel=False)
# The direct extractor bypasses extraction-cache reads, giving independent cold output.
from graphify.extractors.markdown import extract_markdown
cold = extract_markdown(doc)
results["frontmatter_change"] = {"before": first["nodes"], "warm": warm["nodes"], "cold": cold["nodes"]}

caller = CORPUS / "caller.py"
callee = CORPUS / "callee.py"
caller.write_text('from callee import newly_available\n\ndef caller():\n    return newly_available()\n')
callee.write_text('def unrelated():\n    return 1\n')
assert _rebuild_code(CORPUS)
callee.write_text('def unrelated():\n    return 1\n\ndef newly_available():\n    return 2\n')
assert _rebuild_code(CORPUS, changed_paths=[callee])
incremental = _load_graph(str(OUT / "graph.json"))
assert _rebuild_code(CORPUS)
full = _load_graph(str(OUT / "graph.json"))


def calls(G):
    return [dict(source=u, target=v, **d) for u, v, d in G.edges(data=True)
            if d.get("relation") == "calls"]


results["callee_added_unchanged_caller"] = {"partial_calls": calls(incremental), "full_calls": calls(full)}
# Same relative source layout at another root yields portable IDs.
elsewhere = WORK / "another-root"
elsewhere.mkdir()
(elsewhere / "caller.py").write_text(caller.read_text())
(elsewhere / "callee.py").write_text(callee.read_text())
a = extract([caller, callee], root=CORPUS, cache_root=WORK, parallel=False)
b = extract([elsewhere / "caller.py", elsewhere / "callee.py"], root=elsewhere, cache_root=WORK, parallel=False)
results["relocation"] = {"same_ids": sorted(n["id"] for n in a["nodes"]) == sorted(n["id"] for n in b["nodes"])}
(HERE / "freshness-results.json").write_text(json.dumps(results, indent=2) + "\n")
print(json.dumps(results["callee_added_unchanged_caller"], indent=2))

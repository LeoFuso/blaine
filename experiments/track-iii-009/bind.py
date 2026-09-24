"""Data-only binding of unchanged III.8 discovery and III.8R selector."""
import importlib.util
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
OLD=HERE.with_name('track-iii-008')
RECOVERY=HERE.with_name('track-iii-008r')
sys.path.insert(0,str(OLD))
import source
import discover


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value)
    return value


selector=module('iii9_original_selector',RECOVERY/'recover.py')
collector=module('iii9_original_collector',OLD/'build_index.py')
# These assignments change experiment data roots only. No function body is edited.
source.HERE=HERE
selector.HERE=HERE
selector.OLD=HERE
collector.HERE=HERE


def load(name):return json.loads((HERE/name).read_text())
def save(path,data):
    path=Path(path);temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,sort_keys=True,ensure_ascii=False)+'\n');temp.replace(path)


wire=source.wire

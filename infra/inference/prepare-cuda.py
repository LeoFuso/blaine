#!/usr/bin/env python3
"""Bridge the pinned CUDA wheel layout to the layout expected by JIT linking."""
import json
from pathlib import Path
import sys

config = json.loads(Path(sys.argv[1]).read_text())
cuda = Path(config['env']) / 'lib/python3.13/site-packages/nvidia/cu13'
assert (cuda / 'lib/libcudart.so.13').is_file()
for path, target in [(cuda / 'lib64', 'lib'),
                     (cuda / 'lib/libcudart.so', 'libcudart.so.13'),
                     (cuda / 'lib/libcublas.so', 'libcublas.so.13'),
                     (cuda / 'lib/libcublasLt.so', 'libcublasLt.so.13')]:
    assert (path.parent / target).exists(), f'Missing pinned CUDA component: {target}'
    if path.is_symlink():
        assert path.readlink() == Path(target), f'Unexpected CUDA layout: {path}'
    elif path.exists():
        raise RuntimeError(f'Refusing to replace existing CUDA path: {path}')
    else:
        path.symlink_to(target)

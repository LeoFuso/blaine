#!/usr/bin/env python3
"""Bounded local-link/fence/JSON check; repository has no canonical doc checker."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
FILES = ['docs/personal-agent-hub.md', 'docs/roadmap/001-blaine-development-roadmap.md',
         'docs/README.md', 'client/README.md', 'experiments/e0a-blaine-client/README.md',
         'experiments/e0a-blaine-client/language.md']
links = anchors = 0
for name in FILES:
    path = ROOT / name
    source = path.read_text()
    assert len(re.findall(r'^```', source, re.M)) % 2 == 0, name
    for block in re.findall(r'```json\s*\n(.*?)```', source, re.S):
        json.loads(block)
    text = re.sub(r'```.*?```', '', source, flags=re.S)
    for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
        if re.match(r'[a-z]+:', target):
            continue
        file, _, anchor = target.partition('#')
        dest = (path.parent / file).resolve() if file else path
        assert dest.exists(), (name, target)
        links += 1
        if anchor and dest.suffix == '.md':
            content = dest.read_text()
            headings = re.findall(r'^#+ (.+)$', content, re.M)
            ids = {re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-') for heading in headings}
            ids.update(re.findall(r'id="([^"]+)"', content))
            assert anchor in ids, (name, target, 'anchor missing')
            anchors += 1
json.loads((ROOT / 'experiments/e0a-blaine-client/request.json').read_text())
print(f'PASS: {len(FILES)} documents; {links} local links; {anchors} anchors; fences and JSON parsed')

"""Independent literal oracle: JSON only, no imports from the implementation."""
import json


def scan(observables, protected_literals):
    findings = []
    checked = 0
    for audience, outputs in sorted(observables.items()):
        forbidden = sorted({s for domain, literals in protected_literals.items() if domain != audience for s in literals})
        for index, output in enumerate(outputs):
            # Check actual serialized caller-result exports, compact and pretty forms.
            encodings = [json.dumps(output, sort_keys=True, ensure_ascii=False, separators=(',', ':')),
                         json.dumps(output, sort_keys=True, ensure_ascii=False, indent=2)]
            hits = [literal for literal in forbidden if any(literal in value for value in encodings)]
            checked += 1
            if hits:
                findings.append({'audience': audience, 'output_index': index, 'literals': hits})
    return {'status': 'FAIL' if findings else 'PASS', 'outputs_scanned': checked,
            'leaking_outputs': len(findings), 'findings': findings}

#!/usr/bin/env python3
"""Deterministic Policy C report over authoritative retained evidence.

Reads the append-only execution event record to discover routing artifacts, then
reads those content-addressed artifacts. It never reads durable runtime state,
which expires, and never asks a model to count. A model may explain this report;
it must not compute it.

    python3 scripts/routing-report.py --data ~/.local/share/blaine/runtime/data --since 14d
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore  # noqa: E402
from runtime.kernel.routing import POLICY, POLICY_VERSION  # noqa: E402

# Below this many observations the report states insufficiency instead of
# publishing a rate. The gate is deterministic; no model decides it.
MINIMUM_SAMPLE = 20
REFERENCE = re.compile(r'artifact://([A-Za-z0-9_-]{1,80})/sha256:[0-9a-f]{64}')


def since_cutoff(value: str | None):
    if not value:
        return None
    match = re.fullmatch(r'(\d+)([dh])', value)
    if not match:
        raise SystemExit('--since expects a value such as 14d or 36h')
    span = timedelta(days=int(match[1])) if match[2] == 'd' else timedelta(hours=int(match[1]))
    return datetime.now(timezone.utc) - span


def routing_records(events: Path, store: ArtifactStore, cutoff):
    """Discover routing artifacts through the permanent event record."""
    seen, records, skipped = set(), [], 0
    if not events.exists():
        return records, skipped
    for line in events.read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            skipped += 1
            continue
        if event.get('producer', {}).get('component') != 'blaine.kernel.routing':
            continue
        if event.get('event_type') != 'artifact.produced':
            continue
        if cutoff and datetime.fromisoformat(event['occurred_at']) < cutoff:
            continue
        for ref in event.get('references', {}).get('artifact_ids', []):
            match = REFERENCE.fullmatch(ref)
            if not match or ref in seen:
                continue
            seen.add(ref)
            try:
                record = json.loads(store.read(match[1], ref))
            except (OSError, ValueError):
                skipped += 1
                continue
            payload = record.get('payload') if record.get('kind') == 'RoutingRecord' else None
            if payload and payload.get('policy') == POLICY:
                records.append(payload)
            else:
                skipped += 1
    return records, skipped


def median(values):
    ordered = sorted(values)
    if not ordered:
        return None
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def rate(part, whole):
    return None if not whole else round(part / whole, 4)


def summarize(records, skipped, cutoff):
    escalated = [r for r in records if r['escalated']]
    recommended = [r for r in records if r['escalation_reason']]
    local_only = [r for r in records if not r['escalated']]
    completed_local = [r for r in local_only if r['outcome'] == 'COMPLETED']
    completed_after = [r for r in escalated if r['outcome'] == 'COMPLETED']
    failed = [r for r in records if r['outcome'] == 'FAILED']
    reasons, admissions = {}, {}
    for record in recommended:
        reasons[record['escalation_reason']] = reasons.get(record['escalation_reason'], 0) + 1
        key = record['escalation_admission']
        admissions[key] = admissions.get(key, 0) + 1
    report = {
        'policy': POLICY, 'policy_version': POLICY_VERSION,
        'window': cutoff.isoformat() if cutoff else 'all retained evidence',
        'source': 'append-only execution events and content-addressed artifacts',
        'sampling_rule': 'every Task that retained a routing record in this window; not a sample',
        'tasks_observed': len(records),
        'externally_bounded': sum(r['externally_bounded'] for r in records),
        'completed_locally': len(completed_local),
        'escalation_recommended': len(recommended),
        'escalated': len(escalated),
        'completed_after_escalation': len(completed_after),
        'failed': len(failed),
        'local_completion_rate': rate(len(completed_local), len(records)),
        'escalation_rate': rate(len(escalated), len(records)),
        'median_local_turns': median([r['local_turns'] for r in local_only]),
        'median_turns_before_escalation': median([r['escalation_iteration'] for r in recommended
                                                  if r['escalation_iteration'] is not None]),
        'escalation_reasons': dict(sorted(reasons.items())),
        'escalation_admissions': dict(sorted(admissions.items())),
        'unreadable_records': skipped,
        'minimum_sample': MINIMUM_SAMPLE,
    }
    # Denominators are explicit, and an insufficient sample is reported rather
    # than dressed up as a finding.
    report['sufficiency'] = ('INSUFFICIENT_SAMPLE' if len(records) < MINIMUM_SAMPLE
                             else 'SUFFICIENT_FOR_RATES')
    report['interpretation_limits'] = [
        'escalation records that another tier was required, not that local inference was incapable',
        'failure causes are unclassified; raw provenance is retained for later attribution',
        'rates describe the retained population above, not any wider workload',
    ]
    return report


def main():
    parser = argparse.ArgumentParser(description='Deterministic Policy C routing report')
    parser.add_argument('--data', type=Path, required=True,
                        help='runtime data directory containing artifacts/ and events.jsonl')
    parser.add_argument('--since', help='bounded window such as 14d or 36h')
    arguments = parser.parse_args()
    cutoff = since_cutoff(arguments.since)
    store = ArtifactStore(arguments.data / 'artifacts')
    records, skipped = routing_records(arguments.data / 'events.jsonl', store, cutoff)
    print(json.dumps(summarize(records, skipped, cutoff), indent=1))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

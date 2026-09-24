"""Preparation for the later Jev-vs-accepted routing carveout (roadmap C3).

This is deliberately not a benchmark program and it runs nothing by itself. It
fixes the record shape and the aggregation rules now, so a future comparison over
approximately 20-30 real Blaine Tasks produces evidence that can be reviewed
instead of a one-off script's opinion.

Comparison happens in shadow mode: the accepted classifier keeps deciding, the
candidate only observes, and disagreement is a recorded label rather than a
routing change. Monetary cost stays UNKNOWN on both sides, because the provider
exposes no cost field and local serving has no per-call price; latency and token
counts are the observable proxies.
"""
import json
import os
from pathlib import Path

MINIMUM_SAMPLE = 20      # roadmap C3 asks for approximately 20-30 real Tasks
SUITABILITIES = ('UNDERPOWERED', 'JUST_RIGHT', 'OVERKILL')
REQUIRED = {'task_id', 'binding_id', 'accepted_suitability', 'candidate_suitability',
            'agreement', 'candidate_failure'}
OPTIONAL = {'workload', 'candidate_reason', 'candidate_latency_ms', 'candidate_input_tokens',
            'candidate_output_tokens', 'human_label', 'recorded_at'}


def validate_observation(record: dict) -> dict:
    """One comparison row. Unknown fields and invented labels are rejected."""
    if not isinstance(record, dict) or not REQUIRED <= set(record) or set(record) - (REQUIRED | OPTIONAL):
        raise ValueError('Unknown or missing comparison fields')
    if record['accepted_suitability'] not in SUITABILITIES:
        raise ValueError('Accepted suitability outside the existing vocabulary')
    candidate = record['candidate_suitability']
    if candidate is not None and candidate not in SUITABILITIES:
        raise ValueError('Candidate suitability outside the existing vocabulary')
    if (candidate is None) != (record['candidate_failure'] is not None):
        raise ValueError('A candidate row is either an answer or a bounded failure')
    if record.get('human_label') is not None and record['human_label'] not in SUITABILITIES:
        raise ValueError('Human evaluation label outside the existing vocabulary')
    return record


def sink(path: Path):
    """Append-only JSONL recorder, matching the existing evidence sinks."""
    def record(observation: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('ab', buffering=0) as stream:
            stream.write(json.dumps(validate_observation(observation), sort_keys=True).encode() + b'\n')
            os.fsync(stream.fileno())
    return record


def aggregate(records) -> dict:
    """Summarize without concluding. Below the sample floor nothing is decided."""
    rows = [validate_observation(record) for record in records]
    answered = [row for row in rows if row['candidate_suitability'] is not None]
    labelled = [row for row in answered if row.get('human_label') is not None]
    latencies = sorted(row['candidate_latency_ms'] for row in answered
                       if row.get('candidate_latency_ms') is not None)
    failures = {}
    for row in rows:
        if row['candidate_failure']:
            failures[row['candidate_failure']] = failures.get(row['candidate_failure'], 0) + 1
    confusion = {}
    for row in answered:
        key = f"{row['accepted_suitability']}->{row['candidate_suitability']}"
        confusion[key] = confusion.get(key, 0) + 1
    summary = {
        'version': 1, 'observations': len(rows), 'candidate_answered': len(answered),
        'candidate_failures': failures,
        'agreement_with_accepted': round(sum(row['agreement'] is True for row in answered) / len(answered), 4)
        if answered else None,
        'confusion_accepted_to_candidate': confusion,
        'human_labelled': len(labelled),
        'accepted_error_vs_label': round(sum(row['accepted_suitability'] != row['human_label']
                                             for row in labelled) / len(labelled), 4) if labelled else None,
        'candidate_error_vs_label': round(sum(row['candidate_suitability'] != row['human_label']
                                              for row in labelled) / len(labelled), 4) if labelled else None,
        'candidate_latency_ms': {'count': len(latencies),
                                 'median': latencies[len(latencies) // 2] if latencies else None,
                                 'max': latencies[-1] if latencies else None},
        'monetary_cost': 'UNKNOWN on both sides; no provider cost field and no local per-call price',
        'minimum_sample': MINIMUM_SAMPLE,
        'routing_changed_by_this_comparison': False,
    }
    summary['verdict'] = ('INSUFFICIENT_SAMPLE' if len(rows) < MINIMUM_SAMPLE
                          else 'UNLABELLED' if not labelled else 'READY_FOR_REVIEW')
    # Adoption requires measured benefit reviewed by a human; this never decides it.
    summary['adoption_decision'] = 'NOT_MADE_HERE'
    return summary

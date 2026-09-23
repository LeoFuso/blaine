#!/usr/bin/env python3
"""Controlled live Restate fixture. Never cancels a user Task or responds for a human."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runtime.personal_agent import PersonalAgent, RestateBinding, decision_request, task_identity

REQUEST = 'e0c-direct-session-independence-20260923'
QUESTION = 'Controlled E0.C lifecycle acceptance: retain this human wait across workstation transport disconnects.'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('operation', choices=['prepare', 'observe', 'cleanup'])
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    agent = PersonalAgent(RestateBinding())
    task = task_identity(REQUEST)
    if args.operation == 'prepare':
        receipt = agent.execute({'operation': 'create', 'request_id': REQUEST,
                                 'task_request': decision_request(REQUEST, QUESTION)})
        if receipt['task_id'] != task:
            raise RuntimeError('Unexpected fixture Task identity')
    if args.operation == 'cleanup':
        # Only the deterministic fixture identity is accepted, never an argument.
        agent.execute({'operation': 'cancel', 'task_id': task})
    expected = 'CANCELLED' if args.operation == 'cleanup' else 'WAITING'
    deadline = time.monotonic() + 15
    while True:
        state = agent.execute({'operation': 'inspect', 'task_id': task})
        if state.get('lifecycle') == expected:
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Authoritative fixture lifecycle did not match')
        time.sleep(.2)
    result = {'operation': args.operation, 'task_id': task, 'authoritative_state': state,
              'scope': 'Controlled live Task snapshot; compare before/after actual session termination'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'task_id': task, 'lifecycle': state['lifecycle'], 'operation': args.operation}))


if __name__ == '__main__':
    main()

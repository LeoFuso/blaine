"""Completion Contract / E1.0 native Restate acceptance suite (HOST-bound).

Invokes the existing authoritative acceptance harness
``experiments/personal-agent-hub/e1-0/accept.py`` against a real Restate server.
The harness is isolated: it binds dedicated loopback ports, owns and stops only
the processes it starts, and rewrites its own evidence. The suite does not copy
that logic; it only supplies the toolchain environment and declares the host
resources it uses.

Prerequisites (probe-gated; BLOCKED, never provisioned):
  * restate -- restate-server binary + runtime venv (the SDK).
"""
from verification.suite import Step, Suite, VerificationClass

SUITE = Suite(
    name='completion-contract-native',
    verification_class=VerificationClass.HOST,
    description='E1.0 Completion Contract acceptance on a real Restate server with SIGKILLs.',
    steps=[
        Step(name='e1-0-acceptance',
             command=['BLAINE_PYTHON', 'experiments/personal-agent-hub/e1-0/accept.py',
                      '--restate-server', 'BLAINE_RESTATE_SERVER',
                      '--output', 'BLAINE_E10_OUTPUT'],
             timeout=900.0,
             # Substituted at submit time from the probed toolchain:
             #   BLAINE_PYTHON          -> runtime venv python (carries restate-sdk)
             #   BLAINE_RESTATE_SERVER  -> restate-server binary
             #   BLAINE_E10_OUTPUT      -> fresh scratch dir for this run
             env={'BLAINE_E10_OUTPUT': ''}),
    ],
    resources=('restate-runtime',),
    prereq_probes=('restate',),
)

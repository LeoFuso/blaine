"""Sample HERMETIC suite that validates the orchestration plumbing itself.

It runs a trivial deterministic pytest selection against the verification
package (the scheduler unit tests) with no host services. This exists to prove
the suite/discovery/report machinery end to end; it is not a production gate.
"""
from verification.suite import Step, Suite, VerificationClass

SUITE = Suite(
    name='sample-hermetic',
    verification_class=VerificationClass.HERMETIC,
    description='Deterministic sample suite validating the verification plumbing.',
    steps=[
        Step(name='scheduler-self-test',
             command=['BLAINE_PYTHON', '-m', 'pytest', 'verification/tests.py', '-q'],
             env={'BLAINE_PYTHON': ''}),
    ],
    resources=(),
    prereq_probes=(),
)

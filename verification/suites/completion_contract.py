"""Completion Contract / E1 hermetic suite.

First production consumer of the verification system: the E1.0 Completion
Contract kernel tests. These are pure unit/contract tests that run from any
checkout with no host services. The existing pytest/unittest substrate is
reused as-is; this suite only names and sequences the authoritative commands.

The command uses the ``BLAINE_PYTHON`` placeholder, which the executor
substitutes from the environment (default: the shared runtime venv python).
"""
from verification.suite import Step, Suite, VerificationClass

SUITE = Suite(
    name='completion-contract',
    verification_class=VerificationClass.HERMETIC,
    description='E1.0 Completion Contract kernel: contract, verifier and legality semantics (hermetic).',
    steps=[
        Step(name='completion-contract-unit',
             command=['BLAINE_PYTHON', '-m', 'pytest',
                      'tests/test_completion_contract.py',
                      'tests/test_completion_workflow.py',
                      'tests/test_regression_coverage.py', '-q'],
             env={'BLAINE_PYTHON': ''}),
    ],
    resources=(),
    prereq_probes=(),
)

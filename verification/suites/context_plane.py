"""Current Context Plane and integrated kernel regressions, without host services.

This registers the merged CP.1 regression surface with the canonical harness.
A passing regression suite does not qualify CP.2's unapproved storage boundary
or replace required native persistence evidence.
"""
from verification.suite import Step, Suite, VerificationClass

SUITE = Suite(
    name='context-plane',
    verification_class=VerificationClass.HERMETIC,
    description='Context Plane and integrated kernel regressions; not CP.2 storage acceptance.',
    steps=[Step(name='context-plane-kernel-regressions',
                command=['BLAINE_PYTHON', '-m', 'pytest', 'tests', '-q'])],
    resources=(),
    prereq_probes=(),
)

"""CP.2 native writes/readback/restart through trusted HOST scheduling.

Publish this definition and probes_mirix.py as reviewed verification infrastructure.
The candidate worktree supplies only the executed test/production subject; none of
its Python is imported into the trusted scheduler process.
"""
from verification import probes_mirix  # noqa: F401 -- register the trusted probe
from verification.suite import Step, Suite, VerificationClass

SUITE = Suite(
    name='context-plane-memory-native',
    verification_class=VerificationClass.HOST,
    description='CP.2 governed MIRIX persistence, scoped replay, service restart and compiled context.',
    steps=[Step(name='context-plane-memory-native',
                command=['BLAINE_PYTHON', 'experiments/context-plane-cp2/accept_native.py'],
                timeout=600.0)],
    resources=('restate-runtime', 'mirix'),
    prereq_probes=('restate', 'mirix-cp2'),
)

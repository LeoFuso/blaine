"""Declared execution-control capabilities of the paths Blaine actually integrates.

Each claim states its support level, its finest real granularity and the class of
evidence behind it. Nothing here is aspirational: an absent or UNSUPPORTED claim
means Blaine must not attempt the behavior, and must not emulate it either.
Provider-specific adapters declare their own profiles next to their bindings.
"""
from runtime.kernel.instrument import (
    ADMIT_CONTINUATION, AdapterProfile, CapabilityClaim, INTERRUPT_EXECUTION,
    OBSERVE_CONTINUATION, OBSERVE_MODEL, OBSERVE_TOOL, REBIND_EFFORT, REBIND_MODEL,
    STEER_CONTINUATION,
)


def claim(capability, support, granularity, evidence, note=''):
    return CapabilityClaim(capability, support, granularity, evidence, note)


# Blaine owns this loop end to end: cognition, policy admission, one capability
# execution, verification, then the next cognition. Control therefore returns to
# Blaine before every model continuation, inside the durable runtime.
BLAINE_KERNEL_LOOP = AdapterProfile('blaine-kernel-loop', 'blaine.kernel.workflow', (
    claim(OBSERVE_CONTINUATION, 'OBSERVED', 'continuation', 'live',
          'Each workflow iteration begins at a continuation boundary.'),
    claim(ADMIT_CONTINUATION, 'OBSERVED', 'continuation', 'live',
          'Admission runs in a journaled step before cognition; replay reuses it.'),
    claim(OBSERVE_MODEL, 'OBSERVED', 'continuation', 'live',
          'One cognition call per iteration, with adapter-supplied token usage.'),
    claim(OBSERVE_TOOL, 'OBSERVED', 'continuation', 'live',
          'One admitted capability execution per iteration.'),
    claim(STEER_CONTINUATION, 'OBSERVED', 'continuation', 'live',
          'Durable external input resolves a promise consumed at the next boundary.'),
    claim(INTERRUPT_EXECUTION, 'OBSERVED', 'continuation', 'live',
          'Restate invocation cancellation is delivered at a durable await.'),
    # Binding changes are representable but no admitted path changes them today;
    # claiming them would overstate what this increment demonstrates.
    claim(REBIND_MODEL, 'UNSUPPORTED', None, 'none',
          'Cognition binding is deployment configuration, not a runtime control.'),
    claim(REBIND_EFFORT, 'UNSUPPORTED', None, 'none',
          'No reasoning-effort control is exposed by the local chat binding.'),
))

# A single bounded text-only dispatch with no tools and no inherited session.
# Nothing inside it is observable, so no continuation claim is made.
GOOSE_WORKER = AdapterProfile('goose-worker', 'goose-cli', (
    claim(OBSERVE_CONTINUATION, 'UNSUPPORTED', None, 'none',
          'One-shot single-turn dispatch exposes no internal continuation.'),
    claim(ADMIT_CONTINUATION, 'UNSUPPORTED', None, 'none',
          'The harness never returns control to Blaine mid-execution.'),
    claim(OBSERVE_MODEL, 'INFERRED', 'worker_dispatch', 'live',
          'One dispatch is configured for one turn; per-call usage is not reported.'),
    claim(OBSERVE_TOOL, 'UNSUPPORTED', None, 'none', 'Tools are disabled for this seam.'),
    claim(STEER_CONTINUATION, 'UNSUPPORTED', None, 'none', 'No input channel during execution.'),
    claim(INTERRUPT_EXECUTION, 'OBSERVED', 'worker_dispatch', 'live',
          'Blaine owns the child process and terminates the dispatch.'),
    claim(REBIND_MODEL, 'OBSERVED', 'worker_dispatch', 'live',
          'The operator deployment selects the model per dispatch, never WorkerInput.'),
    claim(REBIND_EFFORT, 'UNSUPPORTED', None, 'none', 'No effort control is exposed.'),
))

PROFILES = {profile.adapter_id: profile for profile in (BLAINE_KERNEL_LOOP, GOOSE_WORKER)}

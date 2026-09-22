"""Continuation boundary, telemetry isolation and control-path policy controls."""
import hashlib
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.kernel import workflow
from runtime.kernel.adapter_profiles import BLAINE_KERNEL_LOOP, GOOSE_WORKER
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.cognition import ScriptedCognition
from runtime.kernel.contracts import message
from runtime.kernel.execution import Capabilities
from runtime.kernel.instrument import (
    ADMIT_CONTINUATION, AdapterProfile, CapabilityClaim, ContinuationBoundary, ControlPath,
    ControlPathError, ExecutionIdentity, Instrumentation, MemoryRecorder, NoopObserver,
    NullRecorder, OBSERVE_CONTINUATION, OBSERVE_MODEL, REBIND_EFFORT, REBIND_MODEL, SafeRecorder,
    UnsupportedCapability, evidence_digest, model_attributes, safe, validate_assessment,
)

SECRET = 'SECRET_FIXTURE_DO_NOT_EMIT'
GOOD = hashlib.sha256(b'GOOD').hexdigest()


class Registry:
    def __init__(self, *a): self.handlers = {}
    def main(self, **kw):
        def accept(f): self.run = f; return f
        return accept
    def handler(self, **kw):
        def accept(f): self.handlers[f.__name__] = f; return f
        return accept


class Context:
    """Records journal step names and can replay them without re-execution."""
    def __init__(self, journal=None, replay=False):
        self.saved, self.steps, self.journal, self.replay = {}, [], journal if journal is not None else {}, replay

    def key(self): return 'control'
    def request(self): return SimpleNamespace(id='local-test-invocation')
    def set(self, k, v): self.saved[k] = v

    async def run_typed(self, name, fn, *options, **kw):
        self.steps.append(name)
        if self.replay and name in self.journal:
            return deepcopy(self.journal[name])
        value = fn(**kw)
        self.journal[name] = deepcopy(value)
        return value


def spec(content=b'GOOD'):
    return message('TaskSpec', {'objective': 'Produce the exact deliverable.',
        'completion': [{'criterion': 'Exact', 'evidence': {'artifact': 'answer',
            'sha256': hashlib.sha256(content).hexdigest()}}],
        'capabilities': ['artifact.write'], 'autonomy': {'allowed': ['artifact.write']}})


async def run_task(instrumentation=None, contents=('DRAFT', 'GOOD'), context=None, recorder=None):
    with tempfile.TemporaryDirectory() as directory:
        store = ArtifactStore(Path(directory) / 'artifacts')
        capabilities = Capabilities(store, Path(directory) / 'effects.sqlite', recorder=recorder)
        actions = [{'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                    'input': {'name': 'answer', 'content': value}} for value in contents]
        with patch.object(workflow.restate, 'Workflow', Registry):
            service = workflow.create_workflow(store, ScriptedCognition(actions), capabilities,
                                               instrumentation=instrumentation)
        ctx = context or Context()
        return await service.run(ctx, spec()), ctx


class DisabledInstrumentationTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_bundle_is_inert(self):
        self.assertFalse(Instrumentation().enabled)
        self.assertIsInstance(Instrumentation().recorder, NullRecorder)

    async def test_no_journal_entry_span_or_behavior_change_when_disabled(self):
        baseline, plain = await run_task()
        explicit, bundled = await run_task(Instrumentation())
        self.assertEqual(baseline, explicit)
        self.assertEqual(plain.steps, bundled.steps)
        self.assertFalse([step for step in plain.steps if step.startswith('continuation/')])
        self.assertEqual(baseline['payload']['outcome'], 'COMPLETED')

    async def test_completion_contract_semantics_are_unchanged(self):
        recorder = MemoryRecorder()
        instrumented, _ = await run_task(Instrumentation(recorder=safe(recorder),
                                                         control=ControlPath((NoopObserver(),))))
        plain, _ = await run_task()
        self.assertEqual(plain['payload'], instrumented['payload'])
        verifier = [r for r in recorder.records if r.get('kind') == 'verifier']
        self.assertEqual([r['attributes']['blaine.verifier.outcome'] for r in verifier],
                         ['unsatisfied', 'unsatisfied', 'unsatisfied', 'satisfied'])


class CorrelationTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self):
        recorder = MemoryRecorder()
        result, ctx = await run_task(Instrumentation(recorder=safe(recorder)), recorder=recorder)
        return recorder, result, ctx

    async def test_model_and_tool_spans_carry_task_and_session_identity(self):
        recorder, _, _ = await self.exercise()
        models = [r for r in recorder.records if r.get('kind') == 'model_invocation']
        tools = [r for r in recorder.records if r.get('kind') == 'tool_execution']
        self.assertEqual(len(models), 2)
        self.assertEqual(len(tools), 2)
        for record in models + tools:
            self.assertEqual(record['attributes']['blaine.task_id'], 'control')
            self.assertEqual(record['attributes']['blaine.run_id'], 'run:local-test-invocation')
        self.assertEqual([r['attributes']['blaine.model_invocation_id'] for r in models],
                         ['control/1', 'control/2'])
        self.assertEqual([r['attributes']['blaine.capability_call_id'] for r in tools],
                         ['control/1', 'control/2'])
        self.assertEqual([r['attributes']['gen_ai.tool.name'] for r in tools],
                         ['artifact.write', 'artifact.write'])

    async def test_boundary_events_precede_their_continuation_in_causal_order(self):
        recorder, _, _ = await self.exercise()
        order = [(r['order'], r['type'], r.get('name'), r.get('kind')) for r in recorder.records]
        boundaries = [o for o in order if o[2] == 'blaine.continuation.boundary']
        models = [o for o in order if o[3] == 'model_invocation']
        tools = [o for o in order if o[3] == 'tool_execution']
        self.assertEqual(len(boundaries), 2)
        # boundary N -> model invocation N -> tool N -> boundary N+1
        self.assertLess(boundaries[0][0], models[0][0])
        self.assertLess(models[0][0], tools[0][0])
        self.assertLess(tools[0][0], boundaries[1][0])
        self.assertLess(boundaries[1][0], models[1][0])
        events = [r for r in recorder.records if r.get('name') == 'blaine.continuation.boundary']
        self.assertEqual([e['attributes']['blaine.continuation.index'] for e in events], [0, 1])
        self.assertEqual([e['attributes']['blaine.continuation.reason'] for e in events],
                         ['session_start', 'tool_results'])
        self.assertEqual([e['attributes']['blaine.continuation.tool_invocations'] for e in events], [0, 1])
        self.assertEqual(events[1]['attributes']['blaine.continuation.last_tool_outcome'], 'success')

    async def test_evidence_progress_is_observable_without_content(self):
        recorder, _, _ = await self.exercise()
        events = [r for r in recorder.records if r.get('name') == 'blaine.continuation.boundary']
        digests = [e['attributes'].get('blaine.continuation.evidence_digest') for e in events]
        self.assertEqual(digests[0], evidence_digest({}))
        self.assertNotEqual(digests[0], digests[1])
        self.assertTrue(all(len(d) == 64 for d in digests if d))


class TelemetryIsolationTests(unittest.IsolatedAsyncioTestCase):
    async def test_recorder_failure_does_not_fail_the_task(self):
        class Broken:
            dropped_total = 0
            def span(self, name, *, kind, attributes): raise RuntimeError('exporter down')
            def event(self, name, *, attributes): raise RuntimeError('exporter down')
            def count(self, name, value=1, attributes=None): raise RuntimeError('exporter down')
        recorder = SafeRecorder(Broken())
        result, _ = await run_task(Instrumentation(recorder=recorder), recorder=recorder)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertGreater(recorder.dropped_total, 0)

    async def test_span_body_exception_still_propagates_through_a_broken_recorder(self):
        recorder = SafeRecorder(type('B', (), {
            'span': lambda self, name, *, kind, attributes: (_ for _ in ()).throw(RuntimeError()),
            'event': lambda self, name, *, attributes: None,
            'count': lambda self, name, value=1, attributes=None: None})())
        with self.assertRaises(ValueError):
            with recorder.span('x', kind='verifier', attributes={}):
                raise ValueError('real failure')

    async def test_dense_telemetry_does_not_synchronously_export(self):
        try:
            from runtime.kernel.telemetry_otel import recorder as build
        except ImportError:  # pragma: no cover
            self.skipTest('OpenTelemetry SDK is not installed')
        built, shutdown = build('http://127.0.0.1:1', timeout_ms=200)
        if isinstance(built, NullRecorder):
            self.skipTest('OpenTelemetry SDK is not installed')
        try:
            began = time.monotonic()
            result, _ = await run_task(Instrumentation(recorder=safe(built)), recorder=built)
            elapsed = time.monotonic() - began
        finally:
            stopping = time.monotonic()
            drained = shutdown()
            flush = time.monotonic() - stopping
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        # An unroutable Collector must not add latency to the execution path, and
        # shutdown with buffered telemetry stays inside its budget, reporting
        # honestly that the buffer was not drained.
        self.assertLess(elapsed, 2.0)
        self.assertLess(flush, 2.0)
        # Shutdown reports whether the buffer drained instead of assuming it did.
        self.assertIsInstance(drained, bool)

    async def test_no_secret_or_content_reaches_telemetry(self):
        recorder = MemoryRecorder()
        result, _ = await run_task(Instrumentation(recorder=safe(recorder)),
                                   contents=(SECRET, 'GOOD'), recorder=recorder)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        emitted = repr(recorder.records)
        self.assertNotIn(SECRET, emitted)
        self.assertNotIn('Produce the exact deliverable', emitted)


class ControlPathTests(unittest.IsolatedAsyncioTestCase):
    def boundary(self):
        return ContinuationBoundary(ExecutionIdentity('task', 'run:1'), 1, 'tool_results',
                                    model_invocations=1, tool_invocations=1, last_tool_outcome='success')

    async def test_observer_runs_synchronously_before_the_next_continuation(self):
        seen = []
        class Recording:
            observer_id = 'recording'
            def inspect(self, boundary):
                seen.append(('observer', boundary.index, boundary.tool_invocations))
                return {'outcome': 'PROCEED', 'label': 'nominal', 'score': 0.25}
        recorder = MemoryRecorder()
        calls = []
        actions = [{'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                    'input': {'name': 'answer', 'content': value}} for value in ('DRAFT', 'GOOD')]
        class Watched:
            def __call__(self, packet):
                seen.append(('model', packet['payload']['iteration'], None))
                calls.append(packet)
                return ScriptedCognition(actions)(packet)
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory) / 'artifacts')
            capabilities = Capabilities(store, Path(directory) / 'effects.sqlite')
            control = ControlPath((Recording(),), recorder=recorder)
            with patch.object(workflow.restate, 'Workflow', Registry):
                service = workflow.create_workflow(store, Watched(), capabilities,
                    instrumentation=Instrumentation(recorder=safe(recorder), control=control))
            result = await service.run(Context(), spec())
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        # Every model continuation is preceded by its boundary observer call.
        self.assertEqual([kind for kind, *_ in seen], ['observer', 'model', 'observer', 'model'])
        self.assertEqual([entry[1] for entry in seen if entry[0] == 'observer'], [0, 1])

    async def test_admitted_decision_is_journaled_and_not_recomputed_on_recovery(self):
        class Counting:
            observer_id = 'counting'
            def __init__(self): self.calls = 0
            def inspect(self, boundary):
                self.calls += 1
                return {'outcome': 'PROCEED', 'label': f'call-{self.calls}'}
        observer = Counting()
        bundle = Instrumentation(control=ControlPath((observer,)))
        journal = {}
        first, ctx = await run_task(bundle, context=Context(journal=journal))
        self.assertEqual(observer.calls, 2)
        self.assertEqual([s for s in ctx.steps if s.startswith('continuation/')],
                         ['continuation/1', 'continuation/2'])
        replayed, replay_ctx = await run_task(bundle, context=Context(journal=journal, replay=True))
        # Recovery observes the already-admitted decision instead of asking again.
        self.assertEqual(observer.calls, 2)
        self.assertEqual(first['payload'], replayed['payload'])
        self.assertEqual(journal['continuation/1']['assessments'][0]['label'], 'call-1')

    async def test_control_failure_policy_is_explicit(self):
        class Broken:
            observer_id = 'broken'
            def inspect(self, boundary): raise RuntimeError('supervisor unavailable')
        recorder = MemoryRecorder()
        record = ControlPath((Broken(),), recorder=recorder).admit(self.boundary())
        self.assertEqual(record['outcome'], 'PROCEED')
        self.assertEqual(record['failures'][0]['failure'], 'observer_error')
        self.assertIn('blaine.control.failed', [r.get('name') for r in recorder.records])
        with self.assertRaises(ControlPathError):
            ControlPath((Broken(),), policy='FAIL_ON_ERROR').admit(self.boundary())
        with self.assertRaises(ValueError):
            ControlPath((Broken(),), policy='IGNORE')

    async def test_control_failure_under_fail_closed_stops_the_task(self):
        class Broken:
            observer_id = 'broken'
            def inspect(self, boundary): raise RuntimeError('supervisor unavailable')
        bundle = Instrumentation(control=ControlPath((Broken(),), policy='FAIL_ON_ERROR'))
        with self.assertRaises(ControlPathError):
            await run_task(bundle)

    async def test_budget_exceeded_poisons_the_observer_without_blocking_forever(self):
        class Slow:
            observer_id = 'slow'
            def inspect(self, boundary): time.sleep(5)
        path = ControlPath((Slow(),), budget_ms=150)
        began = time.monotonic()
        first = path.admit(self.boundary())
        self.assertLess(time.monotonic() - began, 2.0)
        self.assertEqual(first['failures'][0]['failure'], 'budget_exceeded')
        self.assertEqual(path.admit(self.boundary())['failures'][0]['failure'], 'skipped_poisoned')
        path.close()

    async def test_assessment_metadata_is_closed_and_bounded(self):
        validate_assessment({'outcome': 'ABSTAIN', 'score': 0.5, 'label': 'unclear'}, 'o')
        for raw in ({'outcome': 'INTERVENE'}, {'outcome': 'PROCEED', 'score': 2},
                    {'outcome': 'PROCEED', 'raw_prompt': 'x'}, {'label': 'no outcome'},
                    {'outcome': 'PROCEED', 'latency_ms': -1}):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_assessment(raw, 'o')

    async def test_no_intervention_is_admitted_by_this_increment(self):
        record = ControlPath((NoopObserver(),)).admit(self.boundary())
        self.assertIsNone(record['admitted_intervention'])
        self.assertEqual(record['outcome'], 'PROCEED')


class ObserverSecretBoundaryTests(unittest.IsolatedAsyncioTestCase):
    """A supervisor's credentials must never reach telemetry through this seam.

    No live Jev validation ran, so this covers the structural guarantee any
    replaceable observer is held to, rather than one provider's behavior.
    """
    def boundary(self):
        return ContinuationBoundary(ExecutionIdentity('task', 'run:1'), 0, 'session_start')

    async def test_instrumentation_never_reads_the_environment(self):
        import os
        with patch.dict(os.environ, {'TYPESAFE_API_KEY': SECRET}, clear=False):
            recorder = MemoryRecorder()
            record = ControlPath((NoopObserver(),), recorder=recorder).admit(self.boundary())
        self.assertNotIn(SECRET, repr(recorder.records))
        self.assertNotIn(SECRET, repr(record))

    async def test_unknown_assessment_fields_carrying_a_secret_are_rejected(self):
        class Leaky:
            observer_id = 'leaky'
            def inspect(self, boundary):
                return {'outcome': 'PROCEED', 'credential': SECRET}
        recorder = MemoryRecorder()
        record = ControlPath((Leaky(),), recorder=recorder).admit(self.boundary())
        self.assertEqual(record['assessments'], [])
        self.assertEqual(record['failures'][0]['failure'], 'observer_error')
        self.assertNotIn(SECRET, repr(record))
        self.assertNotIn(SECRET, repr(recorder.records))

    async def test_only_the_outcome_of_an_assessment_reaches_telemetry(self):
        class Chatty:
            observer_id = 'chatty'
            def inspect(self, boundary):
                # Free-text fields stay in the durable admission record, which is
                # Task-scoped evidence, and never become span attributes.
                return {'outcome': 'ABSTAIN', 'detail': SECRET, 'label': SECRET, 'score': 0.5}
        recorder = MemoryRecorder()
        record = ControlPath((Chatty(),), recorder=recorder).admit(self.boundary())
        self.assertEqual(record['assessments'][0]['outcome'], 'ABSTAIN')
        self.assertNotIn(SECRET, repr(recorder.records))
        spans = [r for r in recorder.records if r.get('kind') == 'boundary_control']
        self.assertEqual(spans[0]['attributes']['blaine.control.outcome'], 'ABSTAIN')
        self.assertNotIn('detail', repr(spans[0]['attributes']))


class CapabilityHonestyTests(unittest.TestCase):
    def test_unsupported_capability_is_never_emulated(self):
        self.assertFalse(GOOSE_WORKER.supports(OBSERVE_CONTINUATION))
        self.assertFalse(GOOSE_WORKER.supports(ADMIT_CONTINUATION))
        with self.assertRaises(UnsupportedCapability):
            GOOSE_WORKER.require(ADMIT_CONTINUATION)
        self.assertEqual(GOOSE_WORKER.claim(ADMIT_CONTINUATION).support, 'UNSUPPORTED')

    def test_granularity_is_not_silently_widened(self):
        self.assertTrue(GOOSE_WORKER.supports(REBIND_MODEL, 'worker_dispatch'))
        self.assertFalse(GOOSE_WORKER.supports(REBIND_MODEL, 'agent_turn'))
        self.assertFalse(GOOSE_WORKER.supports(REBIND_MODEL, 'continuation'))

    def test_inferred_support_is_not_promoted_to_observed(self):
        claim = GOOSE_WORKER.claim(OBSERVE_MODEL)
        self.assertEqual((claim.support, claim.granularity), ('INFERRED', 'worker_dispatch'))
        self.assertNotEqual(claim.support, 'OBSERVED')

    def test_kernel_loop_declares_the_synchronous_boundary_it_owns(self):
        self.assertTrue(BLAINE_KERNEL_LOOP.supports(ADMIT_CONTINUATION))
        self.assertTrue(BLAINE_KERNEL_LOOP.supports(OBSERVE_CONTINUATION))
        self.assertFalse(BLAINE_KERNEL_LOOP.supports(REBIND_EFFORT, 'worker_dispatch'))

    def test_claims_must_state_support_granularity_and_evidence(self):
        for bad in (('made.up', 'OBSERVED', 'continuation', 'live'),
                    (OBSERVE_MODEL, 'MAYBE', 'continuation', 'live'),
                    (OBSERVE_MODEL, 'OBSERVED', None, 'live'),
                    (OBSERVE_MODEL, 'OBSERVED', 'token', 'live'),
                    (OBSERVE_MODEL, 'OBSERVED', 'continuation', 'none'),
                    (OBSERVE_MODEL, 'UNSUPPORTED', 'continuation', 'none')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                CapabilityClaim(*bad)

    def test_summary_lists_undeclared_capabilities_instead_of_assuming_them(self):
        profile = AdapterProfile('partial', 'fixture', (
            CapabilityClaim(OBSERVE_MODEL, 'OBSERVED', 'agent_turn', 'fixture'),))
        summary = profile.summary()
        self.assertEqual(list(summary['capabilities']), [OBSERVE_MODEL])
        self.assertIn(ADMIT_CONTINUATION, summary['undeclared'])
        self.assertFalse(profile.supports(ADMIT_CONTINUATION))


class AttributeTests(unittest.TestCase):
    def test_model_attributes_use_genai_conventions_and_reject_bad_usage(self):
        attributes = model_attributes(provider='local.vllm', request_model='fixture-model',
            usage={'input_tokens': 12, 'output_tokens': 3, 'cached_input_tokens': 8},
            finish_reason='stop', reasoning_effort='low')
        self.assertEqual(attributes['gen_ai.provider.name'], 'local.vllm')
        self.assertEqual(attributes['gen_ai.usage.cache_read.input_tokens'], 8)
        self.assertEqual(attributes['blaine.model.reasoning_effort'], 'low')
        with self.assertRaises(ValueError):
            model_attributes(provider='p', request_model='m', usage={'input_tokens': -1})

    def test_boundary_validation_is_closed(self):
        identity = ExecutionIdentity('task', 'run:1')
        for bad in ({'index': -1, 'reason': 'tool_results'}, {'index': 0, 'reason': 'token'},
                    {'index': 0, 'reason': 'tool_results', 'model_invocations': -1},
                    {'index': 0, 'reason': 'tool_results', 'evidence_digest': 'short'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                ContinuationBoundary(identity, **bad)


if __name__ == '__main__':
    unittest.main()

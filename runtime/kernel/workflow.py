"""Native Restate execution. Cognition returns data; only this dispatcher acts."""
from collections.abc import Awaitable, Callable, Sequence
from copy import deepcopy
import hashlib
from datetime import timedelta

import restate

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context import ContextProvider, reconstruct
from runtime.kernel.contracts import (
    MAX_PACKET, MAX_TURNS, TaskResult, TaskState, encode, fields, identifier,
    child_task_id, child_request, accept_task_request, spawn_specs, message, text, unpack, validate_spec, validate_result,
)
from runtime.kernel import completion, journal as capability_journal, review
from runtime.kernel.execution import Capabilities, policy_gate
from runtime.kernel.human import validate_response
from runtime.kernel.events import ExecutionEventPublisher, event_identity, safe_prepare, safe_publish
from runtime.kernel.instrument import (
    ExecutionIdentity, Instrumentation, evidence_digest, model_attributes, tool_attributes,
)
from runtime.kernel.routing import (
    LOCAL_BINDING, RoutingRecord, admit_escalation, effective_capabilities,
    escalation_condition, narrow_grant, verifier_signature,
)

CognitiveAdapter = Callable[[dict], dict]
# Deployment-injected probe hook, never selected by a Task/model or exposed by
# the normal handlers. The integration fixture uses durable barriers for SIGKILL.
Checkpoint = Callable[[restate.WorkflowContext, str, TaskState], Awaitable[None]]


def create_workflow(store: ArtifactStore, cognitive: CognitiveAdapter,
                    capabilities: Capabilities, providers: Sequence[ContextProvider] = (),
                    checkpoint: Checkpoint | None = None,
                    event_publisher: ExecutionEventPublisher | None = None,
                    event_producer_revision: str | None = None,
                    instrumentation: Instrumentation | None = None,
                    escalation_cognitive: CognitiveAdapter | None = None,
                    escalation_binding: str | None = None,
                    semantic_reviewer: review.SemanticReviewer | None = None) -> restate.Workflow:
    workflow = restate.Workflow("CognitiveTaskV1")
    # Deployment-selected diagnostics and boundary control. The default bundle is
    # inert: no span, no event, no extra journal entry, no behavior change.
    instruments = instrumentation or Instrumentation()

    @workflow.main(workflow_retention=timedelta(days=7))
    async def run(ctx: restate.WorkflowContext, request: dict) -> dict:
        try:
            task_id = identifier(ctx.key())
            spec, parent, grant = accept_task_request(request, task_id)
            admissible = effective_capabilities(spec, grant)
            mutating = capability_journal.mutating(admissible)
            # Revision 0 exists before any effect; an invalid contract is rejected
            # at intake exactly like an invalid TaskSpec.
            contract = completion.accept_contract(spec, parent, completion.envelope_contract(request),
                                                  task_id, mutating)
        except (ValueError, TypeError) as error:
            raise restate.TerminalError(str(error), status_code=400) from error
        initial_action = request['payload'].get('initial_action') if request.get('kind') == 'TaskRequest' else None
        read_scope = initial_action['input'].get('workspace') if (
            initial_action and initial_action.get('capability') == 'workspace.read'
            and isinstance(initial_action.get('input'), dict)) else None

        async def step(name, function, **kwargs):
            return await ctx.run_typed(name, function, restate.RunOptions(max_attempts=3), **kwargs)

        async def retain(name: str, value: dict) -> str:
            return await step(name, store.put_json, task_id=task_id, value=value)

        state: TaskState = {
            "task_id": task_id, "revision": 0, "lifecycle": "RUNNING", "iteration": 0,
            "active_specialist": "coordinator", "spec_ref": await retain("accept-spec", message("TaskSpec", spec)),
            "decision_id": None, "decision_ref": None, "context_ref": None,
            "observation_ref": None, "wait": None, "artifacts": {},
            "completion_ref": None, "result_ref": None,
            "remaining_children": spec["autonomy"].get("child_tasks", 0), "children": {},
            "invocation_id": ctx.request().id,
            "request_digest": hashlib.sha256(encode(request)).hexdigest(),
            # Policy C. The binding is execution context, never Task data, and a
            # Task without an external grant is recorded as unbounded rather than
            # silently treated as if it had been bounded.
            "grant": grant, "binding": LOCAL_BINDING, "verifier_history": [],
            "escalation": None, "local_turns": 0, "context_refs": [],
            # Completion Contract v1: authority and contract are retained before any
            # effect; the journal starts empty and only this workflow appends to it.
            "authority_ref": await retain("accept-authority", capability_journal.compile_authority(
                task_id, admissible, [read_scope] if isinstance(read_scope, str) else [], grant is not None)),
            "contract_ref": await retain("accept-contract", message("CompletionContract", contract)),
            "contract_revision": 0, "journal_head": None, "journal_length": 0, "semantic_reviews": {},
        }
        if initial_action is not None:
            state['initial_action'] = initial_action
        if parent is not None:
            state["parent"] = parent
        ctx.set("task", message("TaskState", state))
        if checkpoint:
            await checkpoint(ctx, 'contract_retained', deepcopy(state))
        last_evaluation = None
        amendment_rejected = None

        async def record(label: str, entry: dict) -> None:
            # Appended in a journaled step, so replay reproduces the identical chain.
            state['journal_head'] = await step(f'journal/{label}', capability_journal.append, store=store,
                task_id=task_id, head=state['journal_head'], length=state['journal_length'], entry=entry)
            state['journal_length'] += 1
            ctx.set('task', message('TaskState', state))

        def capability_entry(action: dict, phase: str, **extra) -> dict:
            capability = action['capability']
            entry = {'phase': phase, 'decision_id': state['decision_id'], 'capability': capability,
                     'operation_class': capability_journal.operation_class(capability),
                     'provider': 'acp-client' if capability == 'workspace.read' else 'kernel',
                     'operation': 'read_file' if capability == 'workspace.read' else capability,
                     'authority_ref': state['authority_ref'], 'contract_revision': state['contract_revision'], **extra}
            target = action['input'].get('workspace') if isinstance(action.get('input'), dict) else None
            if capability == 'workspace.read' and isinstance(target, str) and target.strip() and len(target.encode()) <= 512:
                entry['workspace_id'] = target
            return entry

        def denied_action(raw: dict) -> dict | None:
            # A denied proposal is journaled whenever it names a capability at all.
            payload = raw.get('payload') if isinstance(raw, dict) else None
            action = payload.get('next_action') if isinstance(payload, dict) else None
            if (isinstance(action, dict) and action.get('type') == 'INVOKE_CAPABILITY'
                    and isinstance(action.get('capability'), str) and action['capability'].strip()
                    and len(action['capability'].encode()) <= 100):
                return action
            return None
        # Optional diagnostics. No Task state, authorization or progression reads
        # these events or the publication result. Keep this deployment option stable
        # for an invocation's lifetime, like its other journal-producing code.
        previous_event = None
        async def emit(label, event_type, outcome, component, refs=None, payload=None, payload_refs=()):
            nonlocal previous_event
            if event_publisher is None:
                return
            invocation_id = ctx.request().id
            run_id = 'run:' + invocation_id
            producer = {'kind': 'deterministic_application', 'component': component}
            if event_producer_revision:
                producer['code_revision'] = event_producer_revision
            event = await step('event-prepare/' + label, safe_prepare,
                task_id=task_id, run_id=run_id, step_id=label, event_type=event_type,
                outcome=outcome, producer=producer, cause=previous_event,
                references={'restate_invocation_id': invocation_id, **(refs or {})},
                payload={'iteration': state['iteration'], **(payload or {})}, payload_refs=payload_refs)
            await step('event-publish/' + label, safe_publish, publisher=event_publisher, event=event)
            previous_event = event_identity(run_id, label)

        await emit('start', 'task.started', 'RUNNING', 'blaine.kernel.workflow', refs={'parent_task_id': parent['task_id']} if parent else None, payload_refs=(state['spec_ref'],))
        concerns = []
        prepared_packet = None
        tool_invocations, last_tool_outcome = 0, None
        def wait_still_bound(wait_id: str) -> bool:
            binding = completion.human_bindings(contract['criteria']).get(wait_id)
            criterion = next((c for c in contract['criteria'] if binding and c['id'] == binding['criterion']), None)
            return criterion is not None and completion.gating(criterion) and 'waiver' not in criterion

        async def await_input(action):
            state["wait"] = {"wait_id": action["wait_id"], "input_type": action["input_type"],
                             "task_revision": state["revision"], "promise": f"input/{state['iteration']}/{action['wait_id']}"}
            if action['input_type'] == 'human_response':
                requirement = completion.human_binding(contract, action['wait_id'])
                state['wait']['request_ref'] = await retain(f"human-request/{state['iteration']}", requirement['request'])
            state["lifecycle"] = "WAITING"
            ctx.set("task", message("TaskState", state))
            if checkpoint:
                await checkpoint(ctx, 'suspended', deepcopy(state))
            while True:
                received = ctx.promise(state["wait"]["promise"], type_hint=dict).value()
                if action['input_type'] != 'human_response' or amendment_rejected == contract['revision'] + 1:
                    received = await received
                    break
                # A human WAITING Task stays amendable: the user may waive or change
                # the very criterion it waits for. Restate journals which one won.
                source, value = await restate.select(input=received,
                    amendment=ctx.promise(f"contract/{contract['revision'] + 1}", type_hint=dict).value())
                if source == 'input':
                    received = value
                    break
                await apply_amendment(value)
                if amendment_rejected == contract['revision'] + 1:
                    continue
                if not wait_still_bound(action['wait_id']):
                    withdrawn = message('HumanWaitWithdrawn', {'request_id': action['wait_id'],
                        'contract_revision': state['contract_revision'], 'contract_ref': state['contract_ref']})
                    state['wait'] = None
                    state['lifecycle'] = 'RUNNING'
                    state['observation_ref'] = await retain(f"withdrawn-input/{state['iteration']}", withdrawn)
                    ctx.set('task', message('TaskState', state))
                    await settle(f"amended-r{state['contract_revision']}")
                    return withdrawn
                await settle(f"amended-r{state['contract_revision']}")
            if action['input_type'] == 'human_response':
                validate_response(received, requirement['request'], task_id)
                response_ref = await retain(f"human-response/{state['iteration']}", received)
                state['human_responses'] = {**state.get('human_responses', {}), action['wait_id']: response_ref}
                state['artifacts'] = {**state['artifacts'], requirement['artifact']: response_ref}
                observation = message('HumanInputReceipt', {'request_id': action['wait_id'],
                    'response_ref': response_ref, 'value': received['payload']['value']})
            else:
                observation = message("ExternalInput", received)
            state["wait"] = None
            state["lifecycle"] = "RUNNING"
            state['observation_ref'] = await retain(f"resumed-input/{state['iteration']}", observation)
            ctx.set('task', message('TaskState', state))
            if checkpoint:
                await checkpoint(ctx, 'resumed', deepcopy(state))
            return observation

        async def apply_amendment(submitted: dict) -> None:
            """Apply one submitted amendment in a journaled step: amendment, then revision."""
            nonlocal contract, amendment_rejected
            to_revision = contract['revision'] + 1
            def admit(submitted, contract, contract_ref, state):
                try:
                    amendment_request = completion.validate_amendment_request(submitted['request'], task_id)
                    if store.read_json(task_id, submitted['action_ref']) != submitted['request']:
                        raise ValueError('Retained human action differs from the submitted amendment')
                    amendment, updated = completion.apply_amendment(contract, contract_ref, amendment_request,
                                                                    submitted['action_ref'], state, mutating)
                except (ValueError, TypeError, KeyError) as error:
                    # The handler validates against this same immutable revision, so
                    # this is a defect path: record it and keep the revision closed.
                    return {'outcome': 'rejected', 'ref': store.put_json(task_id, message(
                        'CompletionContractAmendmentRejection', {'task_id': task_id, 'to_revision': to_revision,
                            'submitted': submitted, 'reason': str(error)[:512]}))}
                amendment_ref = store.put_json(task_id, message('CompletionContractAmendment', amendment))
                sealed = completion.seal(updated, amendment_ref, task_id, mutating)
                return {'outcome': 'applied', 'amendment_ref': amendment_ref, 'contract': sealed,
                        'contract_ref': store.put_json(task_id, message('CompletionContract', sealed))}
            result = await step(f'amend/{to_revision}', admit, submitted=submitted, contract=deepcopy(contract),
                                contract_ref=state['contract_ref'], state=deepcopy(state))
            if result['outcome'] == 'applied':
                contract = result['contract']
                state['contract_ref'], state['contract_revision'] = result['contract_ref'], contract['revision']
                ctx.set('task', message('TaskState', state))
                await emit(f'contract/{to_revision}', 'contract.amended', 'applied', 'blaine.kernel.completion',
                           payload_refs=(result['amendment_ref'], result['contract_ref']))
                if checkpoint:
                    await checkpoint(ctx, 'amended', deepcopy(state))
            else:
                amendment_rejected = to_revision
                await emit(f'contract/{to_revision}', 'contract.amended', 'rejected', 'blaine.kernel.completion',
                           payload_refs=(result['ref'],))

        async def admit_amendments() -> None:
            # Checked at every iteration boundary; revision-named one-shot promises
            # give compare-and-set, and ``peek`` is journaled, so replay agrees.
            while state['lifecycle'] == 'RUNNING' and amendment_rejected != contract['revision'] + 1:
                submitted = await ctx.promise(f"contract/{contract['revision'] + 1}", type_hint=dict).peek()
                if submitted is None:
                    return
                await apply_amendment(submitted)
                if amendment_rejected != contract['revision'] + 1:
                    await settle(f"amended-r{state['contract_revision']}")

        async def settle(phase: str) -> dict:
            """The only path to COMPLETED: evaluate the current revision, then legality.

            A model proposal, worker exit or capability success is neither necessary
            nor sufficient. Semantic reviews run first, as journaled steps, only for
            criteria whose deterministic dependencies already have verdicts.
            """
            nonlocal last_evaluation
            label = f"{phase}/{state['iteration']}"
            def verify(state, contract):
                with instruments.recorder.span('blaine.verifier', kind='verifier', attributes={
                        **ExecutionIdentity(task_id=task_id, run_id='run:' + ctx.request().id).attributes(),
                        'blaine.verifier.phase': phase}) as span:
                    result = completion.evaluate_contract(contract, state['contract_ref'], state, store)
                    span.set(**{'blaine.verifier.outcome': result['payload']['outcome']})
                    return result
            if any(c['verifier']['kind'] == 'semantic_review' for c in contract['criteria']):
                pre = await step(f"pre-evaluation/{label}", lambda state, contract: completion.assess(contract, state, store),
                                 state=deepcopy(state), contract=deepcopy(contract))
                for criterion in completion.semantic_due(contract, pre, state):
                    name = f"{label}/{criterion['id']}"
                    packet = await step(f'semantic-request/{name}', review.request, task_id=task_id,
                        criterion=criterion, contract_revision=contract['revision'],
                        evidence_digest=completion.evidence_digest(state),
                        dependencies=completion.dependency_view(criterion, pre), state=deepcopy(state), store=store)
                    result = await step(f'semantic/{name}', review.call, reviewer=semantic_reviewer, packet=packet)
                    state['semantic_reviews'] = {**state['semantic_reviews'], criterion['id']: {
                        'ref': await retain(f'semantic-result/{name}', result),
                        'request_ref': await retain(f'semantic-packet/{name}', packet),
                        'contract_revision': contract['revision'],
                        'evidence_digest': completion.evidence_digest(state)}}
            evaluation = await step(f"progress/{label}", verify, state=deepcopy(state), contract=deepcopy(contract))
            last_evaluation = evaluation['payload']
            state['completion_ref'] = await retain(f"progress-evidence/{label}", evaluation)
            if evaluation['payload']['outcome'] != 'satisfied':
                # Bounded repetition memory; a deterministic escalation signal,
                # not a judgement about why the verifier keeps refusing.
                state['verifier_history'] = (state['verifier_history'] +
                                             [verifier_signature(evaluation, state['artifacts'])])[-4:]
            if evaluation['payload']['legality']['legal']:
                state['lifecycle'] = 'COMPLETED'
            ctx.set('task', message('TaskState', state))
            await emit('verification/' + label, 'verifier.evaluated', evaluation['payload']['outcome'],
                'blaine.kernel.completion.evaluate_contract', payload_refs=(state['completion_ref'],))
            if checkpoint:
                await checkpoint(ctx, 'verification-' + phase, deepcopy(state))
            if evaluation['payload']['irrecoverable']:
                # The journal is append-only and invariants are unwaivable: no later
                # evidence or amendment can make this contract satisfiable.
                raise restate.TerminalError('Invariant criteria failed: ' + ', '.join(
                    evaluation['payload']['irrecoverable']), status_code=422)
            return evaluation

        try:
            await settle('accepted')
            for iteration in range(1, MAX_TURNS + 1):
                if state['lifecycle'] == 'COMPLETED':
                    break
                state = {**state, "iteration": iteration}
                await admit_amendments()
                if state['lifecycle'] == 'COMPLETED':
                    break
                if state['escalation'] is None:
                    state['local_turns'] = iteration
                    reason = escalation_condition(iteration, state['verifier_history'])
                    if reason is not None:
                        # A deterministic recommendation. Only the trusted boundary
                        # admits it, and only a deployment supplies the binding.
                        admission = admit_escalation(state['grant'],
                                                     escalation_binding if escalation_cognitive else None)
                        state['escalation'] = {'iteration': iteration, 'reason': reason,
                                               'admission': admission['outcome'],
                                               'binding': admission['binding']}
                        if admission['outcome'] == 'admitted':
                            state['binding'] = admission['binding']
                        ctx.set('task', message('TaskState', state))
                        await emit(f'escalation/{iteration}', 'policy.evaluated',
                                   'allow' if admission['outcome'] == 'admitted' else 'deny',
                                   'blaine.kernel.routing')
                # A continuation boundary: prior model/tool activity is incorporated
                # and the next model continuation has not started. Blaine owns this
                # loop, so the admission runs synchronously here, before cognition.
                if instruments.enabled:
                    await step(f'continuation/{iteration}', instruments.admit, payload={
                        'identity': {'task_id': task_id, 'run_id': 'run:' + ctx.request().id,
                                     'model_invocation_id': f'{task_id}/{iteration}'},
                        'index': iteration - 1, 'reason': 'session_start' if iteration == 1 else 'tool_results',
                        'model_invocations': iteration - 1, 'tool_invocations': tool_invocations,
                        'last_tool_outcome': last_tool_outcome,
                        'evidence_digest': evidence_digest(state['artifacts'])})
                packet = prepared_packet or await step(f"context/{iteration}", reconstruct,
                                                       state=deepcopy(state), spec=spec, store=store, providers=providers,
                                                       contract=contract)
                prepared_packet = None
                state["context_ref"] = await retain(f"context-artifact/{iteration}", packet)
                state['context_refs'] = (state['context_refs'] + [state['context_ref']])[-8:]
                ctx.set("task", message("TaskState", state))

                if checkpoint:
                    await checkpoint(ctx, "before_cognition", deepcopy(state))

                def decide() -> dict:
                    # Spans wrap the physical call inside the journaled step, so a
                    # replay that consumes the journal never fabricates inference.
                    with instruments.recorder.span(None, kind='model_invocation', attributes={
                            **ExecutionIdentity(task_id=task_id, run_id='run:' + ctx.request().id,
                                model_invocation_id=f'{task_id}/{iteration}').attributes(),
                            'blaine.continuation.index': iteration - 1,
                            **model_attributes(provider=getattr(cognitive, 'provider', 'blaine.cognition'),
                                               request_model=getattr(cognitive, 'model', 'scripted'))}) as span:
                        # An admitted escalation rebinds cognition inside the same
                        # Task. No second Task, no new lifecycle owner.
                        adapter = (escalation_cognitive if state['escalation']
                                   and state['escalation']['admission'] == 'admitted' else cognitive)
                        raw = (adapter(deepcopy(packet), observe=span.set)
                               if getattr(adapter, 'accepts_observation', False) else adapter(deepcopy(packet)))
                        if len(encode(raw)) > MAX_PACKET:
                            span.fail('decision_size_limit')
                            raise restate.TerminalError("Decision exceeds size limit", status_code=400)
                        return raw

                # The semantic output is journaled before validation, effect
                # admission or handoff. Replay consumes it without calling cognition.
                deterministic = initial_action is not None and iteration == 1
                if deterministic:
                    decision = message('CognitiveDecision', {'task_id': task_id,
                        'task_revision': state['revision'], 'turn_id': f'{task_id}/{iteration}',
                        'next_action': initial_action})
                else:
                    decision = await step(f"cognitive/{iteration}", decide)
                state["decision_id"] = f"{task_id}/{iteration}"
                state["decision_ref"] = await retain(f"decision/{iteration}", decision)
                ctx.set("task", message("TaskState", state))
                if checkpoint:
                    await checkpoint(ctx, "decision", deepcopy(state))

                await emit(f'cognition/{iteration}', 'operation.prepared' if deterministic else 'cognition.decided', 'recorded', 'blaine.kernel.workflow',
                    refs={'decision_id': state['decision_id']}, payload_refs=(state['context_ref'], state['decision_ref']))
                gate = policy_gate(decision, state, spec, state['grant'], contract)
                await emit(f'policy/{iteration}', 'policy.evaluated', gate['outcome'], 'blaine.kernel.execution.policy_gate',
                    refs={'decision_id': state['decision_id']})
                if gate["outcome"] == "deny":
                    observation = message("PolicyDecision", {**gate, "decision_id": state["decision_id"]})
                    if (denied := denied_action(decision)) is not None:
                        reason = (gate['reason'] or 'denied').encode()[:512].decode(errors='ignore') or 'denied'
                        await record(f'{iteration}/denied', capability_entry(denied, 'denied', reason=reason))
                else:
                    action = decision["payload"]["next_action"]
                    match action["type"]:
                        case "INVOKE_CAPABILITY":
                            capability_request = {
                                "task_id": task_id, "operation_id": state["decision_id"],
                                "capability": action["capability"], "input": action["input"],
                            }
                            # Structural invariant: nothing is dispatched without a
                            # preceding admission in the capability journal.
                            await record(f'{iteration}/admitted', capability_entry(action, 'admitted',
                                operation_id=state['decision_id'],
                                request_digest=capability_journal.digest(message("CapabilityRequest", capability_request))))
                            if checkpoint:
                                await checkpoint(ctx, 'admitted', deepcopy(state))
                            def execute_capability(request):
                                with instruments.recorder.span(None, kind='tool_execution', attributes={
                                        **ExecutionIdentity(task_id=task_id, run_id='run:' + ctx.request().id,
                                            capability_call_id=state['decision_id']).attributes(),
                                        'blaine.continuation.index': iteration - 1,
                                        **tool_attributes(name=action['capability'],
                                                          call_id=state['decision_id'],
                                                          tool_type='blaine.capability')}) as span:
                                    result = capabilities.execute(request)
                                    outcome = result['payload']['outcome']
                                    span.set(**{'blaine.tool.outcome': outcome})
                                    if outcome != 'success':
                                        span.fail('capability_failure')
                                    return result
                            observation = await step(f"capability/{iteration}", execute_capability,
                                                     request=message("CapabilityRequest", capability_request))
                            tool_invocations += 1
                            last_tool_outcome = observation['payload']['outcome']
                            state["artifacts"] = {**state["artifacts"], **observation["payload"]["artifacts"]}
                            state['observation_ref'] = await retain(f'effect-observation/{iteration}', observation)
                            ctx.set('task', message('TaskState', state))
                            if action['capability'] != 'workspace.read' or observation['payload']['outcome'] != 'success':
                                await record(f'{iteration}/observed', {'phase': 'observed',
                                    'operation_id': state['decision_id'], 'outcome': observation['payload']['outcome'],
                                    'receipt_ref': state['observation_ref']})
                            if action['capability'] != 'workspace.read':
                                await emit(f'capability/{iteration}', 'capability.finished', observation['payload']['outcome'],
                                    'blaine.kernel.execution.Capabilities', refs={'capability_call_id': state['decision_id'],
                                        **({'worker_session_id': observation['payload']['output']['attempt_id']}
                                           if action['capability'] == 'worker.run' and 'attempt_id' in observation['payload']['output'] else {})},
                                    payload={'capability': action['capability']}, payload_refs=(state['observation_ref'],))
                            if observation['payload']['artifacts']:
                                await emit(f'artifacts/{iteration}', 'artifact.produced', 'recorded', 'blaine.kernel.artifacts.ArtifactStore',
                                    refs={'capability_call_id': state['decision_id'],
                                          'artifact_ids': list(observation['payload']['artifacts'].values())})
                            if checkpoint:
                                await checkpoint(ctx, 'effect_persisted', deepcopy(state))
                            await settle('effect')
                            if (state['lifecycle'] != 'COMPLETED' and action['capability'] == 'workspace.read'
                                    and observation['payload']['outcome'] == 'success'):
                                state['wait'] = {'input_type': 'workspace_result',
                                    'task_revision': state['revision'],
                                    'promise': f"workspace/{iteration}",
                                    'request_ref': observation['payload']['output']['request_ref']}
                                state['lifecycle'] = 'WAITING'
                                ctx.set('task', message('TaskState', state))
                                received = await ctx.promise(state['wait']['promise'], type_hint=dict).value()
                                from runtime.kernel.workspace import validate_read_result
                                accepted = await step(f'workspace-request/{iteration}', store.read_json,
                                    task_id=task_id, ref=state['wait']['request_ref'])
                                content = validate_read_result(received, accepted['payload'])
                                ref = await step(f'workspace-artifact/{iteration}', store.put,
                                    task_id=task_id, content=content.encode())
                                state['artifacts'] = {**state['artifacts'], action['input']['artifact']: ref}
                                from runtime.kernel.workspace import legacy_receipt
                                receipt_ref = await retain(f'workspace-receipt/{iteration}', legacy_receipt(
                                    task_id, state['wait']['request_ref'], accepted['payload'], ref, content))
                                await record(f'{iteration}/observed', {'phase': 'observed',
                                    'operation_id': state['decision_id'], 'outcome': 'success', 'receipt_ref': receipt_ref})
                                if checkpoint:
                                    await checkpoint(ctx, 'receipt_admitted', deepcopy(state))
                                state['wait'] = None
                                state['lifecycle'] = 'RUNNING'
                                # Cognition cites the receipt the Task admitted, not the raw result.
                                observation = message('WorkspaceReadObservation', {
                                    'operation_id': state['decision_id'], 'receipt_ref': receipt_ref,
                                    'artifact': action['input']['artifact'], 'artifact_ref': ref, 'content': content})
                                await emit(f'capability/{iteration}', 'capability.finished', 'success',
                                    'blaine.kernel.workspace', refs={'capability_call_id': state['decision_id']},
                                    payload={'capability': 'workspace.read'})
                                await emit(f'artifacts/{iteration}', 'artifact.produced', 'recorded',
                                    'blaine.kernel.artifacts.ArtifactStore',
                                    refs={'capability_call_id': state['decision_id'], 'artifact_ids': [ref]})
                            # This accepted, scoped capability is a blocking human
                            # interaction. Its admitted effect supplies the event identity.
                            if (state['lifecycle'] != 'COMPLETED' and action['capability'] == 'human.request'
                                    and observation['payload']['outcome'] == 'success'):
                                observation = await await_input({
                                    'wait_id': action['input']['request']['payload']['request_id'],
                                    'input_type': 'human_response'})
                        case "HANDOFF":
                            previous = state["active_specialist"]
                            state["active_specialist"] = action["specialist"]
                            observation = message("HandoffResult", {
                                "from": previous, "to": action["specialist"], "decision_id": state["decision_id"],
                            })
                        case "WAIT":
                            # Compatibility: explicit external waits remain representable.
                            observation = await await_input(action)
                        case "SPAWN_TASK":
                            children = spawn_specs(action)
                            batch = 'task_specs' in action
                            pending = []
                            for slot, child_spec in children:
                                child_id = child_task_id(task_id, state['decision_id'], slot)
                                label = f"{iteration}" + (f"/{slot}" if batch else '')
                                state['remaining_children'] -= 1 + child_spec['autonomy'].get('child_tasks', 0)
                                child_spec_ref = await retain('child-spec/' + label, message('TaskSpec', child_spec))
                                state['children'][child_id] = {'spec_ref': child_spec_ref, 'result_ref': None,
                                    'parent_task_id': task_id, 'decision_id': state['decision_id'], 'slot': slot}
                                pending.append((child_id, slot, child_spec, label))
                            state['wait'] = ({'child_ids': [c[0] for c in pending], 'input_type': 'TaskResults', 'condition': 'ALL_TERMINAL'}
                                             if batch else {'child_id': pending[0][0], 'input_type': 'TaskResult'})
                            state['wait']['task_revision'] = state['revision']
                            state['lifecycle'] = 'WAITING'
                            ctx.set('task', message('TaskState', state))
                            # Creating all native durable futures issues all calls before
                            # any await. Restate owns execution/recovery; no asyncio task pool.
                            calls = [ctx.workflow_call(run, key=child_id,
                                arg=child_request(task_id, state['decision_id'], slot, child_spec,
                                                  narrow_grant(state['grant'], None)))
                                for child_id, slot, child_spec, _ in pending]
                            for child_id, _, _, label in pending:
                                await emit('child-created/' + label, 'task.child_created', 'recorded',
                                    'blaine.kernel.workflow', refs={'child_task_id': child_id},
                                    payload_refs=(state['children'][child_id]['spec_ref'],))
                            await emit(f'children-wait/{iteration}', 'task.suspended', 'WAITING', 'blaine.kernel.workflow')
                            if checkpoint:
                                await checkpoint(ctx, 'children_created', deepcopy(state))
                            outcomes = []
                            invalid_result = False
                            # Aggregate in declared slot order, independent of physical
                            # completion order. Failed Tasks are values, never implicit success.
                            for (child_id, _, _, label), call in zip(pending, calls):
                                try:
                                    observation = await call
                                except restate.TerminalError:
                                    observation = message('TaskResult', {'task_id': child_id, 'outcome': 'FAILED',
                                        'artifacts': {}, 'completion_ref': None, 'concerns': ['Child invocation failed']})
                                try:
                                    result = validate_result(observation, child_id)
                                except (ValueError, TypeError):
                                    # Still join the other launched children; a malformed
                                    # result must not turn the batch into detached work.
                                    invalid_result = True
                                    state['children'][child_id]['result_error'] = 'invalid_result'
                                    ctx.set('task', message('TaskState', state))
                                    await emit('child-result/' + label, 'task.child_observed', 'INVALID',
                                        'blaine.kernel.workflow', refs={'child_task_id': child_id})
                                    continue
                                ref = await retain('child-result/' + label, observation)
                                state['children'][child_id]['result_ref'] = ref
                                ctx.set('task', message('TaskState', state))
                                outcomes.append({'task_id': child_id, 'outcome': result['outcome'],
                                                 'result_ref': ref, 'completion_ref': result['completion_ref']})
                                await emit('child-result/' + label, 'task.child_observed', result['outcome'],
                                    'blaine.kernel.workflow', refs={'child_task_id': child_id}, payload_refs=(ref,))
                                if checkpoint:
                                    await checkpoint(ctx, 'child_result', deepcopy(state))
                            if invalid_result:
                                raise restate.TerminalError('Invalid child result; all launched children joined')
                            if batch:
                                observation = message('ChildTaskResults', {'children': outcomes})
                            # Child evidence is not promoted into the parent's artifacts.
                            state['wait'] = None
                            state['lifecycle'] = 'RUNNING'
                            ctx.set('task', message('TaskState', state))
                            await emit(f'children-resume/{iteration}', 'task.resumed', 'RUNNING', 'blaine.kernel.workflow')
                            if checkpoint:
                                await checkpoint(ctx, 'children_joined', deepcopy(state))
                        case "COMPLETE":
                            # Only a request for the same legality decision as every other path.
                            observation = await settle('request')
                state["observation_ref"] = await retain(f"observation/{iteration}", observation)
                state["revision"] += 1
                ctx.set("task", message("TaskState", state))
                if state['lifecycle'] != 'COMPLETED':
                    await settle('outcome')
                # Commit owner and originating decision together, then create a
                # fresh specialist packet before its next cognitive execution.
                if state["lifecycle"] != "COMPLETED" and gate["outcome"] == "allow" and action["type"] == "HANDOFF":
                    next_state = {**state, "iteration": iteration + 1}
                    next_packet = await step(f"handoff-context/{iteration}", reconstruct,
                                             state=next_state, spec=spec, store=store, providers=providers,
                                             contract=contract)
                    state["context_ref"] = await retain(f"handoff-packet/{iteration}", next_packet)
                    prepared_packet = next_packet
                ctx.set("task", message("TaskState", state))
                if checkpoint:
                    await checkpoint(ctx, "outcome", deepcopy(state))
                if state["lifecycle"] == "COMPLETED":
                    break
            else:
                concerns.append("Turn limit exhausted without verified completion")
                state["lifecycle"] = "FAILED"
        except restate.TerminalError as error:
            concerns.append(f"Execution stopped: {error.message}".encode()[:512].decode(errors="ignore"))
            state["lifecycle"] = "CANCELLED" if error.status_code == 409 and error.message.lower() == 'cancelled' else "FAILED"
            state["wait"] = None
        # Waivers, PolicyGate denials and unmet ADVISORY criteria stay visible.
        if last_evaluation is not None:
            concerns = (concerns + [c for c in last_evaluation['concerns'] if c not in concerns])[:8]
        result: TaskResult = {
            "task_id": task_id, "outcome": state["lifecycle"],
            "artifacts": state["artifacts"], "completion_ref": state["completion_ref"], "concerns": concerns,
        }
        output = message("TaskResult", result)
        validate_result(output, task_id)
        state["result_ref"] = await retain("task-result", output)
        # Authoritative routing evidence. Telemetry may be lost and durable
        # runtime state expires, so what a later routing experiment needs is an
        # artifact, discoverable through the append-only event record.
        escalation = state['escalation']
        record = RoutingRecord(
            task_id=task_id, outcome=state['lifecycle'],
            externally_bounded=state['grant'] is not None,
            effective_capabilities=tuple(sorted(effective_capabilities(spec, state['grant']))),
            initial_binding=LOCAL_BINDING, final_binding=state['binding'],
            local_turns=state['local_turns'], total_turns=state['iteration'],
            escalated=bool(escalation and escalation['admission'] == 'admitted'),
            escalation_iteration=escalation['iteration'] if escalation else None,
            escalation_reason=escalation['reason'] if escalation else None,
            escalation_admission=escalation['admission'] if escalation else None,
            completion_ref=state['completion_ref'], result_ref=state['result_ref'],
            context_refs=tuple(state['context_refs']), concerns=tuple(concerns), usage=None)
        routing_ref = await retain('routing-record', message('RoutingRecord', record.payload()))
        state['routing_ref'] = routing_ref
        ctx.set("task", message("TaskState", state))
        await emit('routing', 'artifact.produced', 'recorded', 'blaine.kernel.routing',
                   refs={'artifact_ids': [routing_ref]})
        await emit('completion', 'completion.finished', state['lifecycle'], 'blaine.kernel.workflow',
            payload_refs=(state['completion_ref'], state['result_ref']))
        return output

    @workflow.handler()
    async def status(ctx: restate.WorkflowSharedContext) -> dict:
        return await ctx.get("task") or message("TaskLookup", {"task_id": ctx.key(), "outcome": "UNAVAILABLE"})

    @workflow.handler()
    async def submit_input(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
        try:
            payload = fields(unpack(request, "ExternalInput"), {"wait_id", "task_revision", "input_type", "value"})
            identifier(payload["wait_id"])
            text(payload["value"], 512)
            if type(payload["task_revision"]) is not int or payload["input_type"] != "text":
                raise ValueError("Invalid input revision/type")
        except (ValueError, TypeError) as error:
            raise restate.TerminalError(str(error), status_code=400) from error
        current = await ctx.get("task")
        if not current or current["payload"]["lifecycle"] != "WAITING":
            raise restate.TerminalError("Task is not waiting", status_code=409)
        wait = current["payload"]["wait"]
        if wait["input_type"] != "text":
            raise restate.TerminalError("This wait is resolved by a child TaskResult", status_code=409)
        if any(payload[key] != wait[key] for key in ("wait_id", "task_revision", "input_type")):
            raise restate.TerminalError("Input does not match current wait", status_code=409)
        # A one-shot, iteration-qualified promise prevents overwrite and reuse
        # of an old answer at a later wait. Receipt is not completion evidence.
        await ctx.promise(wait["promise"], type_hint=dict).resolve(payload)
        return message("InputReceipt", {"wait_id": payload["wait_id"], "outcome": "ACCEPTED"})

    @workflow.handler()
    async def submit_human_response(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
        current = await ctx.get('task')
        if not current or current['payload']['lifecycle'] != 'WAITING':
            raise restate.TerminalError('Task is not waiting', status_code=409)
        state = current['payload']
        wait = state['wait']
        if wait['input_type'] != 'human_response':
            raise restate.TerminalError('Not a human decision wait', status_code=409)
        try:
            accepted = await ctx.run_typed('read-human-request', store.read_json,
                restate.RunOptions(max_attempts=3), task_id=ctx.key(), ref=wait['request_ref'])
            response = validate_response(request, accepted, ctx.key())
        except (ValueError, TypeError) as error:
            raise restate.TerminalError(str(error), status_code=400) from error
        # This controlled input handler is transport-neutral, not a public authenticated UI.
        # Native one-shot resolution deduplicates the wait; only the consumed value is evidence.
        await ctx.promise(wait['promise'], type_hint=dict).resolve(request)
        return message('InputReceipt', {'request_id': response['request_id'], 'outcome': 'ACCEPTED'})

    @workflow.handler()
    async def amend_contract(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
        """Explicit, typed human change of the Completion Contract.

        Compare-and-set by revision: the amendment resolves the one-shot promise
        ``contract/{from_revision + 1}``, so of two amendments to one revision only
        the first is taken, and an identical retry is recognised. The receipt means
        submitted, not applied; the Task's contract_revision shows application.
        """
        task_id = ctx.key()
        current = await ctx.get('task')
        if not current:
            raise restate.TerminalError('Task unavailable', status_code=404)
        state = current['payload']
        try:
            submitted = completion.validate_amendment_request(request, task_id)
        except (ValueError, TypeError) as error:
            raise restate.TerminalError(str(error), status_code=400) from error
        to_revision = submitted['from_revision'] + 1
        promise = ctx.promise(f'contract/{to_revision}', type_hint=dict)
        value = {'request': request,
                 'action_ref': f'artifact://{task_id}/sha256:' + hashlib.sha256(encode(request)).hexdigest()}
        receipt = {'task_id': task_id, 'request_id': submitted['request_id'],
                   'from_revision': submitted['from_revision'], 'to_revision': to_revision}
        existing = await promise.peek()
        if existing is not None:
            if existing == value:
                return message('AmendmentReceipt', {**receipt, 'outcome': 'ALREADY_SUBMITTED'})
            raise restate.TerminalError(f'Contract revision {to_revision} was already amended by another request', status_code=409)
        if state['lifecycle'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
            raise restate.TerminalError('Task is terminal; its contract is closed', status_code=409)
        if submitted['from_revision'] != state.get('contract_revision'):
            raise restate.TerminalError('Stale contract revision', status_code=409)
        def check() -> dict:
            authority = capability_journal.validate_authority(
                store.read_json(task_id, state['authority_ref']), task_id)
            mutating = capability_journal.mutating(authority['capabilities'])
            contract = completion.validate_contract(store.read_json(task_id, state['contract_ref']), task_id, mutating)
            try:
                completion.apply_amendment(contract, state['contract_ref'], submitted, value['action_ref'], state, mutating)
            except completion.AmendmentDenied as error:
                return {'status': 403, 'reason': str(error)}
            except completion.AmendmentConflict as error:
                return {'status': 409, 'reason': str(error)}
            except (ValueError, TypeError) as error:
                return {'status': 400, 'reason': str(error)}
            return {'status': 200, 'reason': None}
        verdict = await ctx.run_typed('check-amendment', check, restate.RunOptions(max_attempts=3))
        if verdict['status'] != 200:
            raise restate.TerminalError(verdict['reason'], status_code=verdict['status'])
        # The submitted request is the retained human action a waiver will cite.
        action_ref = await ctx.run_typed('retain-amendment-request', store.put_json,
            restate.RunOptions(max_attempts=3), task_id=task_id, value=request)
        if action_ref != value['action_ref']:
            raise restate.TerminalError('Amendment action reference mismatch', status_code=500)
        try:
            await promise.resolve(value)
        except restate.TerminalError:
            if await promise.peek() == value:
                return message('AmendmentReceipt', {**receipt, 'outcome': 'ALREADY_SUBMITTED'})
            raise restate.TerminalError(f'Contract revision {to_revision} was already amended by another request', status_code=409)
        return message('AmendmentReceipt', {**receipt, 'outcome': 'SUBMITTED'})

    from runtime.kernel.control import add_control_handlers
    add_control_handlers(workflow, store)
    return workflow

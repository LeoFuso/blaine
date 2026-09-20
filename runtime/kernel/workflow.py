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
from runtime.kernel.execution import Capabilities, evaluate, policy_gate
from runtime.kernel.human import human_requirement, validate_response
from runtime.kernel.events import ExecutionEventPublisher, event_identity, safe_prepare, safe_publish

CognitiveAdapter = Callable[[dict], dict]
# Deployment-injected probe hook, never selected by a Task/model or exposed by
# the normal handlers. The integration fixture uses durable barriers for SIGKILL.
Checkpoint = Callable[[restate.WorkflowContext, str, TaskState], Awaitable[None]]


def create_workflow(store: ArtifactStore, cognitive: CognitiveAdapter,
                    capabilities: Capabilities, providers: Sequence[ContextProvider] = (),
                    checkpoint: Checkpoint | None = None,
                    event_publisher: ExecutionEventPublisher | None = None,
                    event_producer_revision: str | None = None) -> restate.Workflow:
    workflow = restate.Workflow("CognitiveTaskV1")

    @workflow.main(workflow_retention=timedelta(days=7))
    async def run(ctx: restate.WorkflowContext, request: dict) -> dict:
        try:
            task_id = identifier(ctx.key())
            spec, parent = accept_task_request(request, task_id)
            for criterion in spec['completion']:
                evidence = criterion['evidence']
                if evidence.get('verifier') == 'human_response' and evidence['request']['payload']['task_id'] != task_id:
                    raise ValueError('Human request does not belong to this Task')
        except (ValueError, TypeError) as error:
            raise restate.TerminalError(str(error), status_code=400) from error

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
        }
        initial_action = request['payload'].get('initial_action') if request.get('kind') == 'TaskRequest' else None
        if initial_action is not None:
            state['initial_action'] = initial_action
        if parent is not None:
            state["parent"] = parent
        ctx.set("task", message("TaskState", state))
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
        async def await_input(action):
            state["wait"] = {"wait_id": action["wait_id"], "input_type": action["input_type"],
                             "task_revision": state["revision"], "promise": f"input/{state['iteration']}/{action['wait_id']}"}
            if action['input_type'] == 'human_response':
                requirement = human_requirement(spec, action['wait_id'])
                state['wait']['request_ref'] = await retain(f"human-request/{state['iteration']}", requirement['request'])
            state["lifecycle"] = "WAITING"
            ctx.set("task", message("TaskState", state))
            if checkpoint:
                await checkpoint(ctx, 'suspended', deepcopy(state))
            received = await ctx.promise(state["wait"]["promise"], type_hint=dict).value()
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

        async def progress(phase: str):
            # Completion is a verifier-authorized lifecycle transition. A model
            # proposal is neither necessary nor sufficient to authorize it.
            label = f"{phase}/{state['iteration']}"
            evaluation = await step(f"progress/{label}", evaluate,
                spec=spec, state=deepcopy(state), store=store)
            state['completion_ref'] = await retain(f"progress-evidence/{label}", evaluation)
            if evaluation['payload']['outcome'] == 'satisfied':
                state['lifecycle'] = 'COMPLETED'
            ctx.set('task', message('TaskState', state))
            await emit('verification/' + label, 'verifier.evaluated', evaluation['payload']['outcome'],
                'blaine.kernel.execution.evaluate', payload_refs=(state['completion_ref'],))
            if checkpoint:
                await checkpoint(ctx, 'verification-' + phase, deepcopy(state))

        try:
            await progress('accepted')
            for iteration in range(1, MAX_TURNS + 1):
                if state['lifecycle'] == 'COMPLETED':
                    break
                state = {**state, "iteration": iteration}
                packet = prepared_packet or await step(f"context/{iteration}", reconstruct,
                                                       state=deepcopy(state), spec=spec, store=store, providers=providers)
                prepared_packet = None
                state["context_ref"] = await retain(f"context-artifact/{iteration}", packet)
                ctx.set("task", message("TaskState", state))

                if checkpoint:
                    await checkpoint(ctx, "before_cognition", deepcopy(state))

                def decide() -> dict:
                    raw = cognitive(deepcopy(packet))
                    if len(encode(raw)) > MAX_PACKET:
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
                gate = policy_gate(decision, state, spec)
                await emit(f'policy/{iteration}', 'policy.evaluated', gate['outcome'], 'blaine.kernel.execution.policy_gate',
                    refs={'decision_id': state['decision_id']})
                if gate["outcome"] == "deny":
                    observation = message("PolicyDecision", {**gate, "decision_id": state["decision_id"]})
                else:
                    action = decision["payload"]["next_action"]
                    match action["type"]:
                        case "INVOKE_CAPABILITY":
                            capability_request = {
                                "task_id": task_id, "operation_id": state["decision_id"],
                                "capability": action["capability"], "input": action["input"],
                            }
                            observation = await step(f"capability/{iteration}", capabilities.execute,
                                                     request=message("CapabilityRequest", capability_request))
                            state["artifacts"] = {**state["artifacts"], **observation["payload"]["artifacts"]}
                            state['observation_ref'] = await retain(f'effect-observation/{iteration}', observation)
                            ctx.set('task', message('TaskState', state))
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
                            await progress('effect')
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
                                state['wait'] = None
                                state['lifecycle'] = 'RUNNING'
                                observation = received
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
                                arg=child_request(task_id, state['decision_id'], slot, child_spec))
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
                            observation = await step(f"verify/{iteration}", evaluate,
                                                     spec=spec, state=deepcopy(state), store=store)
                            state["completion_ref"] = await retain(f"completion/{iteration}", observation)
                            if observation["payload"]["outcome"] == "satisfied":
                                state["lifecycle"] = "COMPLETED"
                            await emit(f"verification/request/{iteration}", "verifier.evaluated", observation["payload"]["outcome"],
                                "blaine.kernel.execution.evaluate", payload_refs=(state["completion_ref"],))
                state["observation_ref"] = await retain(f"observation/{iteration}", observation)
                state["revision"] += 1
                ctx.set("task", message("TaskState", state))
                if state['lifecycle'] != 'COMPLETED':
                    await progress('outcome')
                # Commit owner and originating decision together, then create a
                # fresh specialist packet before its next cognitive execution.
                if state["lifecycle"] != "COMPLETED" and gate["outcome"] == "allow" and action["type"] == "HANDOFF":
                    next_state = {**state, "iteration": iteration + 1}
                    next_packet = await step(f"handoff-context/{iteration}", reconstruct,
                                             state=next_state, spec=spec, store=store, providers=providers)
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
        result: TaskResult = {
            "task_id": task_id, "outcome": state["lifecycle"],
            "artifacts": state["artifacts"], "completion_ref": state["completion_ref"], "concerns": concerns,
        }
        output = message("TaskResult", result)
        validate_result(output, task_id)
        state["result_ref"] = await retain("task-result", output)
        ctx.set("task", message("TaskState", state))
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

    from runtime.kernel.control import add_control_handlers
    add_control_handlers(workflow, store)
    return workflow

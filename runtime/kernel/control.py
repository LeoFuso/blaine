"""Human-facing projections and controls over the existing workflow state."""
import restate

from runtime.kernel.contracts import fields, message
from runtime.kernel.workspace import validate_read_result


def add_control_handlers(workflow, store):
    async def read(ctx, ref):
        return await ctx.run_typed('read-control-artifact', store.read_json,
            restate.RunOptions(max_attempts=3), task_id=ctx.key(), ref=ref)

    @workflow.handler()
    async def inspect(ctx: restate.WorkflowSharedContext) -> dict:
        current = await ctx.get('task')
        if not current:
            return {'task_id': ctx.key(), 'lifecycle': 'UNAVAILABLE'}
        state = current['payload']
        spec = await read(ctx, state['spec_ref'])
        wait = state['wait']
        view = {'task_id': ctx.key(), 'objective': spec['payload']['objective'],
            'accepted_spec': spec, 'request_digest': state.get('request_digest'),
            'lifecycle': state['lifecycle'], 'revision': state['revision'],
            'blocking_dependency': {k: v for k, v in wait.items() if k != 'promise'} if wait else None,
            'children': state['children'], 'artifacts': state['artifacts'],
            'result_ref': state['result_ref'], 'completion': None, 'result': None,
            'pending_human_decision': None, 'pending_workspace_read': None}
        for name, ref in [('completion', state['completion_ref']), ('result', state['result_ref'])]:
            if ref:
                view[name] = await read(ctx, ref)
        if wait and wait.get('request_ref'):
            if wait['input_type'] == 'human_response':
                view['pending_human_decision'] = await read(ctx, wait['request_ref'])
            elif wait['input_type'] == 'workspace_result':
                view['pending_workspace_read'] = await read(ctx, wait['request_ref'])
        return view

    @workflow.handler()
    async def artifact(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
        try:
            fields(request, {'name'})
            current = await ctx.get('task')
            ref = current['payload']['artifacts'].get(request['name']) if current else None
            if not ref:
                raise restate.TerminalError('Artifact unavailable', status_code=404)
            def read_content() -> str:
                content = store.read(ctx.key(), ref)
                if len(content) > 16384:
                    raise restate.TerminalError('Artifact exceeds control response budget', status_code=400)
                return content.decode('utf-8')
            content = await ctx.run_typed('read-deliverable', read_content,
                restate.RunOptions(max_attempts=3))
            return {'task_id': ctx.key(), 'name': request['name'], 'ref': ref,
                    'content': content}
        except (ValueError, TypeError, UnicodeError) as error:
            raise restate.TerminalError('Invalid artifact request', status_code=400) from error

    @workflow.handler()
    async def cancel(ctx: restate.WorkflowSharedContext) -> dict:
        current = await ctx.get('task')
        if not current:
            raise restate.TerminalError('Task unavailable', status_code=404)
        state = current['payload']
        if state['lifecycle'] in ('COMPLETED', 'FAILED', 'CANCELLED'):
            return {'task_id': ctx.key(), 'outcome': 'ALREADY_TERMINAL', 'lifecycle': state['lifecycle']}
        invocation = state.get('invocation_id')
        if not invocation:
            raise restate.TerminalError('Cancellation identity unavailable for legacy Task', status_code=409)
        # Restate delivers cancellation at a durable await. Receipt is not terminal state.
        ctx.cancel_invocation(invocation)
        return {'task_id': ctx.key(), 'outcome': 'CANCELLATION_REQUESTED'}

    @workflow.handler()
    async def submit_workspace_result(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
        current = await ctx.get('task')
        state = current['payload'] if current else {}
        wait = state.get('wait')
        if state.get('lifecycle') != 'WAITING' or not wait or wait['input_type'] != 'workspace_result':
            raise restate.TerminalError('Task is not waiting for workspace result', status_code=409)
        try:
            accepted = await read(ctx, wait['request_ref'])
            validate_read_result(request, accepted['payload'])
        except (ValueError, TypeError) as error:
            raise restate.TerminalError('Invalid workspace result', status_code=400) from error
        await ctx.promise(wait['promise'], type_hint=dict).resolve(request)
        return message('InputReceipt', {'outcome': 'ACCEPTED'})

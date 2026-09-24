"""Deterministic in-process stand-in for Restate's journal, suspension and replay.

This is not durability evidence; the real SIGKILL acceptance lives in
experiments/personal-agent-hub/e1-0. It does enforce what replay demands of the
workflow: journaled commands are matched in order by kind and name (a mismatch is
nondeterminism and fails loudly), recorded results return without re-execution,
awaiting an unresolved promise suspends the invocation, and promises resolve once.
"""
from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import patch

import restate

from runtime.kernel import workflow


class Suspended(Exception):
    """The invocation awaits an unresolved durable promise."""


class Crash(Exception):
    """A simulated process death at a checkpoint."""


class Registry:
    def __init__(self, *args):
        self.handlers = {}

    def main(self, **kwargs):
        def accept(function):
            self.run = function
            return function
        return accept

    def handler(self, **kwargs):
        def accept(function):
            self.handlers[function.__name__] = function
            return function
        return accept


class Runtime:
    def __init__(self, key):
        self.key, self.journal, self.state, self.promises = key, [], {}, {}
        self.executions, self.invocations, self.result, self.request = Counter(), 0, None, None


class Future:
    def __init__(self, context, name):
        self.context, self.name = context, name

    def __await__(self):
        return self.context.await_promise(self.name).__await__()


class Promise:
    def __init__(self, context, name):
        self.context, self.name = context, name

    async def peek(self):
        return await self.context.peek_promise(self.name)

    def value(self):
        return Future(self.context, self.name)

    async def resolve(self, value):
        promises = self.context.runtime.promises
        if self.name in promises:
            raise restate.TerminalError('promise was already completed', status_code=409)
        promises[self.name] = json.loads(json.dumps(value))


class WorkflowContext:
    """The main handler's context: every command is journaled and replayed in order."""
    def __init__(self, runtime):
        self.runtime, self.cursor = runtime, 0

    def key(self):
        return self.runtime.key

    def request(self):
        return SimpleNamespace(id='inv-' + self.runtime.key)

    def set(self, key, value):
        self.runtime.state[key] = json.loads(json.dumps(value))

    async def get(self, key):
        return deepcopy(self.runtime.state.get(key))

    def replayed(self, kind, name):
        if self.cursor < len(self.runtime.journal):
            entry = self.runtime.journal[self.cursor]
            if entry[:2] != (kind, name):
                raise AssertionError(f'Nondeterministic replay at {self.cursor}: {entry[:2]} != {(kind, name)}')
            self.cursor += 1
            return True, deepcopy(entry[2])
        return False, None

    def record(self, kind, name, value):
        encoded = json.loads(json.dumps(value))  # Restate journals JSON, not objects
        self.runtime.journal.append((kind, name, encoded))
        self.cursor += 1
        return deepcopy(encoded)

    async def run_typed(self, name, function, *options, **kwargs):
        done, value = self.replayed('run', name)
        if done:
            return value
        self.runtime.executions[name] += 1
        return self.record('run', name, function(**kwargs))

    def promise(self, name, type_hint=None):
        return Promise(self, name)

    async def peek_promise(self, name):
        done, value = self.replayed('peek', name)
        if done:
            return value
        return self.record('peek', name, self.runtime.promises.get(name))

    async def await_promise(self, name):
        done, value = self.replayed('await', name)
        if done:
            return value
        if name not in self.runtime.promises:
            raise Suspended(name)
        return self.record('await', name, self.runtime.promises[name])


class SharedContext:
    """A shared handler's context: reads committed state; side effects run directly."""
    def __init__(self, runtime):
        self.runtime = runtime

    def key(self):
        return self.runtime.key

    async def get(self, key):
        return deepcopy(self.runtime.state.get(key))

    async def run_typed(self, name, function, *options, **kwargs):
        return json.loads(json.dumps(function(**kwargs)))

    def promise(self, name, type_hint=None):
        return Promise(self, name)

    async def peek_promise(self, name):
        return deepcopy(self.runtime.promises.get(name))

    def cancel_invocation(self, invocation_id):
        raise NotImplementedError


async def select(**futures):
    context = next(iter(futures.values())).context
    label = json.dumps(sorted((key, future.name) for key, future in futures.items()))
    done, value = context.replayed('select', label)
    if done:
        return value
    for key, future in futures.items():
        if future.name in context.runtime.promises:
            return context.record('select', label, [key, context.runtime.promises[future.name]])
    raise Suspended(label)


class Harness:
    def __init__(self, store, cognitive, capabilities, **options):
        with patch.object(workflow.restate, 'Workflow', Registry):
            self.service = workflow.create_workflow(store, cognitive, capabilities, **options)
        self.tasks = {}

    async def invoke(self, key, request=None):
        """Run (or replay) the Task's main handler until it returns or suspends."""
        runtime = self.tasks.setdefault(key, Runtime(key))
        if request is not None:
            runtime.request = deepcopy(request)
        runtime.invocations += 1
        with patch.object(workflow.restate, 'select', select):
            try:
                runtime.result = await self.service.run(WorkflowContext(runtime), deepcopy(runtime.request))
            except Suspended:
                return None
        return runtime.result

    async def call(self, key, handler, request=None):
        context = SharedContext(self.tasks[key])
        function = self.service.handlers[handler]
        return await (function(context) if request is None else function(context, deepcopy(request)))

    def state(self, key):
        return self.tasks[key].state['task']['payload']

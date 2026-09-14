"""Milestone 002: Restate owns the task, including its human-input wait."""
import asyncio

import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config

from runtime.task import summarize_objective, validate_request

workflow = restate.Workflow("TaskWorkflow")


@workflow.main()
async def run(ctx: restate.WorkflowContext, request: dict) -> dict:
    try:
        objective, _ = validate_request(request)
    except ValueError as error:
        raise restate.TerminalError(str(error), status_code=400) from error
    task = {"task_id": ctx.key(), "objective": objective, "status": "RUNNING"}
    ctx.set("task", task)
    operation = await ctx.run_typed("summarize-objective", summarize_objective, objective=objective)
    task = {**task, "status": "WAITING_FOR_USER", "operation_result": operation,
            "question": "Continue with a message to approve completion."}
    ctx.set("task", task)
    message = await ctx.promise("user-input", type_hint=str).value()
    completed = {**task, "status": "COMPLETED", "result": {**operation, "user_input": message}}
    ctx.set("task", completed)
    return completed


@workflow.handler()
async def status(ctx: restate.WorkflowSharedContext) -> dict:
    return await ctx.get("task") or {"task_id": ctx.key(), "status": "NOT_FOUND"}


@workflow.handler()
async def proceed(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
    message = request.get("message")
    if not isinstance(message, str) or not message.strip():
        raise restate.TerminalError("message must be nonblank", status_code=400)
    task = await ctx.get("task")
    if not task:
        raise restate.TerminalError("Task not found (or not yet initialized)", status_code=404)
    if task["status"] == "COMPLETED":
        return task
    if task["status"] != "WAITING_FOR_USER":
        raise restate.TerminalError("Task is not waiting for input", status_code=409)
    # Restate atomically resolves this one-shot promise; competing submissions
    # cannot overwrite the accepted input. The run handler alone writes state.
    await ctx.promise("user-input", type_hint=str).resolve(message)
    return {"task_id": ctx.key(), "status": "SIGNAL_ACCEPTED"}


app = restate.app([workflow])

if __name__ == "__main__":
    config = Config()
    config.bind = ["127.0.0.1:29080"]
    asyncio.run(serve(app, config))

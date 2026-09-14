"""Milestone 001: one Restate workflow, one operation, one query."""

import asyncio
from datetime import timedelta

import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config

from runtime.task import summarize_objective, validate_request


task_workflow = restate.Workflow("TaskWorkflow")


@task_workflow.main()
async def run(ctx: restate.WorkflowContext, request: dict) -> dict:
    try:
        objective, delay = validate_request(request)
    except ValueError as error:
        raise restate.TerminalError(str(error), status_code=400) from error

    task_id = ctx.key()
    ctx.set("task", {"task_id": task_id, "objective": objective, "status": "RUNNING"})
    result = await ctx.run_typed(
        "summarize-objective", summarize_objective, objective=objective
    )
    # This read-visible checkpoint follows the journaled operation. The timer
    # leaves time to kill either process and inspect recovery of the same task.
    ctx.set("task", {
        "task_id": task_id,
        "objective": objective,
        "status": "RUNNING",
        "phase": "durable-timer",
        "operation_result": result,
    })
    await ctx.sleep(timedelta(seconds=delay))
    completed = {"task_id": task_id, "status": "COMPLETED", "result": result}
    ctx.set("task", completed)
    return completed


@task_workflow.handler()
async def status(ctx: restate.WorkflowSharedContext) -> dict:
    return await ctx.get("task") or {"task_id": ctx.key(), "status": "NOT_FOUND"}


app = restate.app([task_workflow])

if __name__ == "__main__":
    config = Config()
    config.bind = ["127.0.0.1:9080"]
    asyncio.run(serve(app, config))

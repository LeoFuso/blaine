"""Stateless task bridge using the official ACP Python SDK. stdout is ACP only."""
import asyncio
import json
import logging
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler
from uuid import uuid4

from acp import Agent, InitializeResponse, NewSessionResponse, PromptResponse, run_agent
from acp.schema import AgentCapabilities, AgentMessageChunk, Implementation, TextContentBlock

INGRESS = "http://127.0.0.1:28080"
HELP = "Use create task: <objective>, status <task-id>, or continue <task-id>: <message>."
ID = r"[a-zA-Z0-9_-]{1,128}"


def request(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if body is None else {"Content-Type": "application/json"}
    # Loopback traffic must never be sent to an inherited HTTP proxy.
    with build_opener(ProxyHandler({})).open(
        Request(INGRESS + path, data=data, headers=headers, method="POST"), timeout=10
    ) as response:
        return json.load(response)


def parse_command(text):
    if match := re.fullmatch(r"create task:\s*(\S[\s\S]*)", text.strip(), re.I):
        return "create", None, match[1]
    if match := re.fullmatch(rf"status\s+({ID})", text.strip(), re.I):
        return "status", match[1], None
    if match := re.fullmatch(rf"continue\s+({ID}):\s*(\S[\s\S]*)", text.strip(), re.I):
        return "continue", match[1], match[2]
    raise ValueError(HELP)


async def execute(text):
    action, task_id, message = parse_command(text)
    if action == "create":
        task_id = "task-" + uuid4().hex
        try:
            await asyncio.to_thread(request, f"/TaskWorkflow/{task_id}/run/send", {"objective": message})
        except (OSError, URLError) as error:
            raise ValueError(f"Submission uncertain for {task_id}; query this ID before creating again: {error}") from error
    elif action == "continue":
        await asyncio.to_thread(request, f"/TaskWorkflow/{task_id}/proceed", {"message": message})
    # Bounded convenience polling, never owning or waiting for task lifetime.
    for _ in range(40 if action != "status" else 1):
        state = await asyncio.to_thread(request, f"/TaskWorkflow/{task_id}/status")
        if action == "status" or state["status"] == "COMPLETED" or (
            action == "create" and state["status"] == "WAITING_FOR_USER"
        ):
            return state
        await asyncio.sleep(.1)
    return state


class BlaineAgent(Agent):
    def __init__(self):
        self.sessions = set()  # Only ACP identities, never task state.

    def on_connect(self, conn):
        self.conn = conn

    async def initialize(self, protocol_version, **kwargs):
        return InitializeResponse(protocol_version=1, agent_capabilities=AgentCapabilities(),
                                  agent_info=Implementation(name="blaine", version="0.2.0"))

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        session_id = uuid4().hex
        self.sessions.add(session_id)
        return NewSessionResponse(session_id=session_id)

    async def prompt(self, session_id, prompt, **kwargs):
        try:
            if session_id not in self.sessions:
                raise ValueError("Unknown ACP session; create a new session and query your task ID.")
            if any(not isinstance(block, TextContentBlock) for block in prompt):
                raise ValueError("Only text commands are supported. " + HELP)
            result = await execute("\n".join(block.text for block in prompt))
            text = json.dumps(result, ensure_ascii=False)
        except (ValueError, OSError, HTTPError, URLError) as error:
            text = f"Error: {error}"
        await self.conn.session_update(session_id=session_id,
            update=AgentMessageChunk(session_update="agent_message_chunk", content=TextContentBlock(type="text", text=text)))
        return PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id, **kwargs):
        # ACP turn cancellation is not durable-task cancellation.
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)  # Default stream is stderr.
    asyncio.run(run_agent(BlaineAgent()))

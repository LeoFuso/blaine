"""Diagnostic transport control: unchanged Graphify factory + SDK stdio, no CLI wrapper."""
import asyncio
import sys

from graphify.serve import _build_server
from mcp.server.stdio import stdio_server


async def main():
    server = _build_server(sys.argv[1])
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


asyncio.run(main())

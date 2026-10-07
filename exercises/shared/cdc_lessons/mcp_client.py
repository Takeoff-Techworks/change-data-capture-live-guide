"""Run notebook examples through the official MCP SDK's stdio transport."""

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryFile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_tool(session: ClientSession, name: str, **arguments) -> dict:
    result = await session.call_tool(name, arguments)
    if result.isError:
        raise RuntimeError(f"MCP tool {name} failed: {result.content}")
    if result.structuredContent is None:
        raise RuntimeError(f"MCP tool {name} returned no structured result")
    return result.structuredContent


def run_mcp_example(database: Path, example):
    """Run one async example in a scoped subprocess; safe in Windows Jupyter."""

    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "cdc_lessons.mcp_server", "--database", str(database.resolve())],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        # Notebook stderr is an OutStream without an OS file descriptor.
        with TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as errlog:
            try:
                async with (
                    stdio_client(parameters, errlog=errlog) as (read, write),
                    ClientSession(read, write, read_timeout_seconds=timedelta(seconds=20)) as session,
                ):
                    await session.initialize()
                    return await example(session)
            finally:
                errlog.seek(0)
                diagnostics = errlog.read()
                if diagnostics:
                    sys.stderr.write(diagnostics)

    # Jupyter already owns an event loop; Windows kernels may use a selector loop
    # without subprocess support. A worker gets a separate subprocess-capable loop.
    def run_in_worker():
        loop_factory = (
            asyncio.ProactorEventLoop if sys.platform == "win32" else asyncio.new_event_loop
        )
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            return runner.run(run())

    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(run_in_worker).result()

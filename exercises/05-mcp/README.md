# Session 5 — MCP

Run [lesson_05_mcp_cdc_agent_gateway.ipynb](lesson_05_mcp_cdc_agent_gateway.ipynb)
from top to bottom. Allow approximately 10–15 minutes.

From the repository root, with your virtual environment active:

```bash
pip install -e '.[dev,notebooks]'
jupyter notebook exercises/05-mcp/
```

The notebook creates its own temporary SQLite database; running session 4 first is
helpful but optional. Discover the tool schemas, update a referral, compare current
state with retained history, and inspect evidence, freshness, and access denials.

The shared [`app/mcp/`](../../app/mcp/) gateway is local, in-process, read-only,
and allowlisted. It models MCP-style discovery and tool calls; it does not implement
a networked MCP server or protocol transport.

See the [notebook guide](../../docs/notebook-guide.md) for details and troubleshooting.
Restart the kernel and run all cells to recreate the notebook database.

# OReilly Live Course: Change Data Capture in Action with SQL Server and PostgreSQL

## Hands-on exercises

**Get started**: Setup the lab environment with [Docker](/docker/)

Follow the [exercise index](exercises/README.md) for sessions 2–5 of the live course:

| Session | Start here |
| --- | --- |
| 02 — SQL Server | [Inspect CDC in the SQL Server container](exercises/02-sqlserver/README.md) |
| 03 — PostgreSQL | [Logical replication and Debezium over HTTP](exercises/03-postgres/README.md) |
| 04 — CDC for AI | [RAG and agent-context freshness](exercises/04-cdc-for-ai/README.md) |
| 05 — MCP | [Trace changes through an agent gateway](exercises/05-mcp/README.md) |

Optional integration walkthroughs run the web app on
[SQL Server](exercises/02-sqlserver/BONUS.md)
or [PostgreSQL](exercises/03-postgres/BONUS.md).

## Repository map

| Path | Purpose |
| --- | --- |
| [`app/`](app/README.md) | Shared FastAPI demo, CDC pipeline, projections, AI context, and local MCP-style gateway |
| [`scripts/`](scripts/) | Seed, reset, simulate, process, and replay demo events |
| [`docker/`](docker/README.md) | Compose stacks, Dockerfile, database initialization, Debezium configuration, and receivers |
| [`exercises/`](exercises/README.md) | Walkthroughs, SQL, bridge scripts, and notebooks grouped by course session |
| [`tests/`](tests/) | Application and helper tests with source-specific CDC fixtures |

Run application, notebook, and documented Docker commands from the repository root.
Use the explicit Compose paths in the [Docker stack guide](docker/README.md).

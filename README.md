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

## Run the lab

Pick one option. All commands run from the repository root.

### Docker (local)

Requires Docker with Compose v2 (about 8 GB RAM for SQL Server and PostgreSQL).

```bash
docker compose -f docker/database-capture/compose.yaml up --build -d
docker compose -f docker/database-capture/compose.yaml down   # stop; add -v to wipe data
```

See the [Docker stack guide](docker/README.md) for the other stacks.
To run the web demo without Docker: `pip install -e ".[dev,postgres]"` then `make run`.

### GitHub Codespaces

1. Select **Code → Codespaces → Create codespace on main**.
2. Wait for setup to finish (installs Python dependencies and Docker-in-Docker).
3. Start the stack: the container does not start automatically. Run the Docker commands above in the codespace terminal
   (for SQL Server only, follow the start steps in the [session 2 exercise](exercises/02-sqlserver/README.md)). Forwarded ports
   (8000 web demo, 3000 receiver, 15432 PostgreSQL, 1435 SQL Server) appear in the **Ports** tab.

A 2-core / 8 GB RAM machine works; use 4 cores / 16 GB if available for smoother startup.

### Dev container (local VS Code)

1. Install Docker and the VS Code *Dev Containers* extension.
2. Open the repository and run **Dev Containers: Reopen in Container**.
3. Use the same Docker commands in the integrated terminal.

The configuration lives in [`.devcontainer/devcontainer.json`](.devcontainer/devcontainer.json).

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

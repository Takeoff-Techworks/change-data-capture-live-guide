# Course exercises

The directories contain exercises for sessions 2–5 in the
[course assets](https://drive.google.com/drive/folders/1cW_ivpZy2Hu8W3vK62mC95ZkuLRUMfcx).
Run commands from the repository root and use the [Docker stack guide](../docker/README.md)
to select infrastructure. The [demo app](../app/README.md) is shared across sessions.

| Session | Exercise | Prerequisites |
| --- | --- | --- |
| [02 — SQL Server](02-sqlserver/README.md) | Inspect native CDC, row images, LSNs, capture jobs, and retention; [Python bonus](02-sqlserver/BONUS.md) | Docker Compose and Bash; Python and ODBC for the bonus |
| [03 — PostgreSQL](03-postgres/README.md) | Logical replication, Debezium HTTP capture, recovery; optional app continuation | Docker Compose, `psql`, `jq`; Python for app continuation |
| [04 — CDC for AI](04-cdc-for-ai/README.md) | Stale vs refreshed agent context and freshness budgets | Python and the `notebooks` extra |
| [05 — MCP](05-mcp/README.md) | Current state, history, tool discovery, and access denials | Python and the `notebooks` extra |

Sessions 2 and 3 use separate lab databases; they do not require completing each
other. Each notebook creates its own temporary SQLite database. Read session 4
before session 5 for the freshness vocabulary.


# Docker stacks

Run all commands below from the repository root. The default
[web demo](../app/README.md) and sessions 4–5 notebooks do not require Docker.

## Directory map

| Path | Purpose |
| --- | --- |
| [database-capture/](database-capture/README.md) | Sessions 2–3 SQL Server and PostgreSQL CDC labs, both using the Northstar seed |
| [postgres-app-integration/](postgres-app-integration/README.md) | Session 3 PostgreSQL appointments capture and optional Northstar forwarding |
| [optional-postgres/](optional-postgres/README.md) | Minimal standalone PostgreSQL logical-WAL scaffold profile |

## Stack summary

| Stack | Compose file | Compose project name | Main services | Host ports |
| --- | --- | --- | --- | --- |
| Database capture | [`database-capture/compose.yaml`](database-capture/compose.yaml) | `change-data-capture-oreilly-live` | `postgres`, `postgres-init`, `cdc-receiver`, `debezium`, `sqlserver`, `sqlserver-init` | PostgreSQL `localhost:15432`, SQL Server `1435`, receiver `3000` |
| PostgreSQL app integration | [`postgres-app-integration/compose.yaml`](postgres-app-integration/compose.yaml) | `northstar-postgres-seed-lab` | `postgres`, `receiver`, `debezium` (`capture`), `debezium-app` (`app-capture`) | PostgreSQL `localhost:15432`; receiver internal (`receiver:8081`) |
| Optional PostgreSQL scaffold | [`optional-postgres/compose.yaml`](optional-postgres/compose.yaml) | `change-data-capture-guide` | `postgres` (`postgres-debezium` profile) | No published ports |

## Database capture

```bash
dc() { docker compose -f docker/database-capture/compose.yaml "$@"; }
dc config --quiet
docker compose up --build -d
```

Start SQL Server only:

```bash
dc up -d sqlserver
dc run --rm sqlserver-init
```

Start PostgreSQL only:

```bash
dc up -d --build postgres cdc-receiver debezium
```

Key configuration and implementation files:

- [`database-capture/sqlserver/init.sql`](database-capture/sqlserver/init.sql)
- [`postgres-app-integration/postgres/init.sql`](postgres-app-integration/postgres/init.sql)
- [`database-capture/debezium/application.properties`](database-capture/debezium/application.properties)
- [`database-capture/receiver/Dockerfile`](database-capture/receiver/Dockerfile)
- [`database-capture/receiver/receiver.py`](database-capture/receiver/receiver.py)

## PostgreSQL app integration

```bash
dc() { docker compose -f docker/postgres-app-integration/compose.yaml "$@"; }
dc config --quiet
dc up -d postgres receiver
```

After completing [session 3 setup](../exercises/03-postgres/README.md), start one
capture profile:

```bash
dc --profile capture up -d debezium
# or
dc --profile app-capture up -d debezium-app
```

Key configuration and implementation files:

- [`postgres-app-integration/config/postgres-debezium.properties`](postgres-app-integration/config/postgres-debezium.properties)
- [`postgres-app-integration/config/postgres-debezium-app.properties`](postgres-app-integration/config/postgres-debezium-app.properties)
- [`postgres-app-integration/receiver/debezium_http_receiver.py`](postgres-app-integration/receiver/debezium_http_receiver.py)

## Optional PostgreSQL scaffold

```bash
docker compose -f docker/optional-postgres/compose.yaml --profile postgres-debezium up -d
docker compose -f docker/optional-postgres/compose.yaml down
```

This scaffold is intentionally minimal and is not a full course lab by itself.

## State and teardown

All stacks keep state in named volumes by default.

- `docker compose ... down` keeps named volumes.
- `docker compose ... down -v` removes volumes for that stack (database data and connector offsets where applicable).

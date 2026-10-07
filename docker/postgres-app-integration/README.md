# PostgreSQL and Northstar integration stack

This stack supports [session 3](../../exercises/03-postgres/README.md): capture
appointment changes with Debezium Server over HTTP, inspect the event journal,
and optionally forward a captured change into Northstar.

From the repository root:

```bash
dc() { docker compose -f docker/postgres-app-integration/compose.yaml "$@"; }
dc config --quiet
dc up -d postgres receiver
```

The Compose initializer provisions the Northstar source tables and matching seed,
creates the `debezium` role/publication, and configures full appointment row
images. It runs on the first initialization of this stack's fresh named volume.
Start `debezium` after verifying the seed in the walkthrough; `debezium-app`
remains the separate app-continuation capture profile.

| File | Purpose |
| --- | --- |
| [`compose.yaml`](compose.yaml) | PostgreSQL, journal receiver, and two capture profiles |
| [`postgres/init.sql`](postgres/init.sql) | Shared Northstar source schema and seed |
| [`config/postgres-debezium.properties`](config/postgres-debezium.properties) | Capture `northstar_cdc_lab` appointments |
| [`config/postgres-debezium-app.properties`](config/postgres-debezium-app.properties) | Capture `northstar_app` appointments with separate offsets |
| [`receiver/debezium_http_receiver.py`](receiver/debezium_http_receiver.py) | Receive and journal events; forward a selected update to the app |

PostgreSQL is available at `localhost:15432`. The receiver is internal to the Docker
network at `receiver:8081`. `dc down` preserves data; `dc down -v` removes this
stack's databases, journal, and offsets.

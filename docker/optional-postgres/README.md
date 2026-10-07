# Optional PostgreSQL scaffold

This preserves the original root Compose scaffold. It starts a PostgreSQL source
with logical WAL enabled, without a published port, receiver, or connector.
Use the [Docker stack guide](../README.md) to choose a complete course lab.

From the repository root:

```bash
docker compose -f docker/optional-postgres/compose.yaml --profile postgres-debezium up -d
docker compose -f docker/optional-postgres/compose.yaml down
```
